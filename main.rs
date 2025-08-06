use std::{
    fs::File,
    io::{self, BufRead, BufReader, Write},
    thread,
    time::{Duration, Instant},
};

use rdev::{listen, EventType, Key};
use rfd::FileDialog;
use windows::{
    Win32::UI::Input::KeyboardAndMouse::{
        SendInput, INPUT, INPUT_MOUSE, MOUSEINPUT, MOUSEEVENTF_ABSOLUTE, MOUSEEVENTF_MOVE,
    },
    Win32::UI::WindowsAndMessaging::{GetSystemMetrics, SM_CXSCREEN, SM_CYSCREEN},
};

fn parse_file(path: &str) -> Vec<(i32, i32, f64)> {
    let file = File::open(path).expect("Failed to open file");
    let reader = BufReader::new(file);
    let mut actions = Vec::new();

    let screen_width = unsafe { GetSystemMetrics(SM_CXSCREEN) };
    let screen_height = unsafe { GetSystemMetrics(SM_CYSCREEN) };
    let grid_size = 625;
    let cell_size = grid_size / 3;
    let grid_start_x = screen_width / 2 - grid_size / 2;
    let grid_start_y = screen_height / 2 - grid_size / 2;

    for line in reader.lines() {
        if let Ok(line) = line {
            let parts: Vec<&str> = line.trim().split('|').collect();
            if parts.len() < 3 {
                continue;
            }

            let col: f64 = match parts[0].parse() {
                Ok(v) => v,
                Err(_) => continue,
            };

            let row: f64 = match parts[1].parse() {
                Ok(v) => v,
                Err(_) => continue,
            };

            if let Ok(note_time_ms) = parts[2].parse::<f64>() {
                let x = grid_start_x as f64 + col * cell_size as f64 + cell_size as f64 / 2.0;
                let y = grid_start_y as f64 + row * cell_size as f64 + cell_size as f64 / 2.0;
                actions.push((x.round() as i32, y.round() as i32, note_time_ms / 1000.0));
            }
        }
    }

    actions
}
fn send_absolute_mouse_move(screen_x: i32, screen_y: i32) {
    let screen_width = unsafe { GetSystemMetrics(SM_CXSCREEN) };
    let screen_height = unsafe { GetSystemMetrics(SM_CYSCREEN) };

    let normalized_x = ((screen_x as f64 / screen_width as f64) * 65535.0).round() as i32;
    let normalized_y = ((screen_y as f64 / screen_height as f64) * 65535.0).round() as i32;

    let input = INPUT {
        r#type: INPUT_MOUSE,
        Anonymous: unsafe {
            std::mem::transmute(MOUSEINPUT {
                dx: normalized_x,
                dy: normalized_y,
                mouseData: 0,
                dwFlags: MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE,
                time: 0,
                dwExtraInfo: 0,
            })
        },
    };

    unsafe {
        SendInput(&[input], std::mem::size_of::<INPUT>() as i32);
    }
}
fn run_macro(actions: Vec<(i32, i32, f64)>, sleep_before_start: Duration) {
    println!("Starting in {:.2} seconds...", sleep_before_start.as_secs_f64());
    thread::sleep(sleep_before_start);
    let start = Instant::now();

    for (x, y, note_time) in actions {
        let target = Duration::from_secs_f64(note_time);
        let now = Instant::now();
        if target > now.duration_since(start) {
            thread::sleep(target - now.duration_since(start));
        }

        send_absolute_mouse_move(x, y);
    }
}

fn choose_sleep_duration() -> Duration {
    let default_sleep = Duration::from_secs_f64(4.1);
    println!("Choose sleep preset before start:");
    println!("1) Default {:.2} seconds", default_sleep.as_secs_f64());
    println!("2) Custom (enter seconds)");
    print!("Enter choice (1 or 2): ");
    io::stdout().flush().unwrap();

    let mut choice = String::new();
    io::stdin().read_line(&mut choice).expect("Failed to read input");
    let choice = choice.trim();

    match choice {
        "1" => default_sleep,
        "2" => {
            print!("Enter custom sleep duration in seconds (e.g. 3.5): ");
            io::stdout().flush().unwrap();
            let mut custom_input = String::new();
            io::stdin().read_line(&mut custom_input).expect("Failed to read input");
            match custom_input.trim().parse::<f64>() {
                Ok(seconds) if seconds >= 0.0 => Duration::from_secs_f64(seconds),
                _ => {
                    println!("Invalid input, using default {:.2} seconds", default_sleep.as_secs_f64());
                    default_sleep
                }
            }
        }
        _ => {
            println!("Invalid choice, using default {:.2} seconds", default_sleep.as_secs_f64());
            default_sleep
        }
    }
}

fn wait_for_keypress() -> Option<Key> {
    use std::sync::mpsc::channel;

    let (tx, rx) = channel();

    thread::spawn(move || {
        listen(move |event| {
            if let EventType::KeyPress(key) = event.event_type {
                let _ = tx.send(key);
            }
        })
        .expect("Failed to listen for keyboard");
    });

    rx.recv().ok()
}

fn main() {
    loop {
        println!("Please select the TXT file with notes...");

        let file_path = FileDialog::new()
            .add_filter("Text files", &["txt"])
            .set_title("Select your notes TXT file")
            .pick_file();

        let path = match file_path {
            Some(path) => path.to_string_lossy().to_string(),
            None => {
                println!("No file selected, exiting.");
                return;
            }
        };

        println!("Selected file: {}", path);

        let sleep_before_start = choose_sleep_duration();

        println!("Press SPACE to start...");

        // Wait for SPACE to start
        loop {
            if let Some(key) = wait_for_keypress() {
                if key == Key::Space {
                    break;
                }
            }
        }

        let actions = parse_file(&path);
        run_macro(actions, sleep_before_start);

        println!("Finished macro for file: {}", path);
        println!("Press R to restart with a new file, or Q to quit.");

        // Wait for R or Q keypress
        loop {
            if let Some(key) = wait_for_keypress() {
                if key == Key::KeyR {
                    println!("Restarting...");
                    break; // will restart loop
                } else if key == Key::KeyQ {
                    println!("Quitting.");
                    return;
                }
            }
        }
    }
}