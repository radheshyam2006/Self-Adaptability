import os
import subprocess
import time
import glob

def split_and_run():
    input_file = "corner_names"

    # CLEANUP: Remove old part files and done markers
    old_part_files = glob.glob(f"{input_file}.part*")
    for f in old_part_files:
        try:
            os.remove(f)
            print(f"Removed old file: {f}")
        except Exception as e:
            print(f"Failed to remove {f}: {e}")

    # Read all lines from corner_names
    try:
        with open(input_file, 'r') as f:
            lines = [line.strip() for line in f.readlines()]
    except FileNotFoundError:
        print(f"Error: {input_file} not found!")
        return

    total_lines = len(lines)
    num_parts = 5
    lines_per_part = total_lines // num_parts
    extra_lines = total_lines % num_parts

    part_filenames = []

    # SPLIT + LAUNCH
    for part in range(num_parts):
        start_index = part * lines_per_part + (part if part < extra_lines else extra_lines)
        end_index = start_index + lines_per_part - 1 + (1 if part < extra_lines else 0)
        part_lines = lines[start_index:end_index + 1]

        part_filename = f"{input_file}.part{part + 1:02d}"
        part_filenames.append(part_filename)

        # Write the part file
        with open(part_filename, 'w') as pf:
            pf.writelines(line + '\n' for line in part_lines)

        print(f"Written part: {part_filename} (Lines: {len(part_lines)})")

        # Launch in new terminal
        try:
            subprocess.run(
                f"gnome-terminal -- python3 corner_run_part.py {part_filename}",
                shell=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Failed to launch terminal for {part_filename}: {e}")

    print(" All parts started. Now waiting for completion...")

    # WAIT LOOP: Check for all .done files
    pending = set(part_filenames)
    while pending:
        finished = []
        for pf in pending:
            done_marker = f"{pf}.done"
            if os.path.exists(done_marker):
                print(f" {done_marker} detected.")
                finished.append(pf)
        pending -= set(finished)
        if pending:
            time.sleep(5)

    print(" All parts have finished!")

    # FINAL CHECK: Look for missing generated.raw files
    print("\nChecking generated.raw files for all corners...\n")
    raw_gen = 1
    for corner in lines:
        raw_path = os.path.join(corner, "generated.raw")
        if not os.path.exists(raw_path):
            print(f"[ERROR] {corner}: Raw file not generated.")
            print(f"        Investigate by running this command inside '{corner}':")
            print(f"        spectre -64 +l spectre.log +lqt 0 +lqs +lsusp ++aps generated.scs\n")
            raw_gen = 0
    if(raw_gen):
        print("All raw files generated successfully")
        

if __name__ == "__main__":
    split_and_run()

