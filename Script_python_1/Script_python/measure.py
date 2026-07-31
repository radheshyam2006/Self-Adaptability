import os
import subprocess
import time
import signal

NUM_PARTS = 5
flag_files = []
terminal_processes = {}

for i in range(1, NUM_PARTS + 1):
    part_num = f"{i:02d}"
    filename = f"corner_names.part{part_num}"

    if not os.path.exists(filename):
        continue

    ocn_filename = f"measure_{part_num}.ocn"
    flag_filename = f"done_measure_{part_num}.flag"
    flag_files.append(flag_filename)

    # Remove existing ocn file & flag file if they exist
    if os.path.exists(ocn_filename):
        os.remove(ocn_filename)
    if os.path.exists(flag_filename):
        os.remove(flag_filename)

    try:
        with open(filename, "r") as in1, open(ocn_filename, "a") as out:
            # Initialize the output file for Ocean script
            out.write(f'of = outfile("./Result_tran_{part_num}.out" "w")\n')
            out.write('fprintf(of, "\\t\\t\\t")\n')

            # Extract headers from Measure_spec
            with open("Measure_spec", "r") as in2:
                for line in in2:
                    if line.strip():
                        header = line.strip().split()[0]  # Extract the first word
                        out.write(f'fprintf(of, " {header} ")\n')
            out.write('fprintf(of, "\\n")\n')

            # Process each corner in the current part file
            for corner_name in in1:
                corner_name = corner_name.strip()
                out.write(f'fprintf(of, " {corner_name} ")\n')
                out.write(f'openResults("{corner_name}/generated.raw")\n')
                out.write("selectResult('sp)\n")

                # Process variables in Measure_spec again for this corner
                with open("Measure_spec", "r") as in3:
                    for line in in3:
                        if line.strip():
                            variable = line.strip().split()[0]
                            remaining = line.strip().split(" ", 1)[1] if " " in line.strip() else ""
                            out.write(f"{variable} = {remaining}\n")
                            out.write(f'fprintf(of, "\\t %e", {variable})\n')
                out.write('fprintf(of, "\\n")\n')

            # Add flag creation at the end
            out.write('close(of)\n')
            out.write(f'system(sprintf(nil "touch {flag_filename}"))\n')
            out.write('exit()\n')  # <- THIS forces Virtuoso to fully exit


    except FileNotFoundError as e:
        print(f"Error: {e}")
        continue

    # Launch Virtuoso in a new terminal and load the Ocean script
    cmd = f"virtuoso -nograph -restore \"{ocn_filename}\""
    proc = subprocess.Popen(
        ["gnome-terminal", "--", "bash", "-c", cmd],
        start_new_session=True
    )


    print(f"Launched: {ocn_filename} (Terminal PID: {proc.pid})")
    terminal_processes[flag_filename] = proc

print("All jobs launched. Monitoring completion via flag files...")


# Monitoring loop (wait for flags and close the corresponding terminal)
remaining_flags = set(flag_files)
while remaining_flags:
    for flag in list(remaining_flags):
        if os.path.exists(flag):
            print(f"Detected completion: {flag}")
            proc = terminal_processes.get(flag)
            if proc:
                try:
                    print(f"Force closing terminal (PID: {proc.pid}) for {flag}")
                    os.kill(proc.pid, signal.SIGKILL)  #  Force kill the terminal
                except Exception as e:
                    print(f"Warning: Couldn't close terminal for {flag}: {e}")
            remaining_flags.remove(flag)
    time.sleep(5)

print("All Ocean scripts completed and terminals are force closed.")

