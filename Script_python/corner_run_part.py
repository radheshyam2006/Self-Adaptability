import os
import sys
import shutil
from pathlib import Path

# Check if the filename is provided
if len(sys.argv) != 2:
    print("Usage: python script.py filename")
    sys.exit(1)

filename = sys.argv[1]

# Check if the file exists
if not os.path.exists(filename):
    print(f"{filename}: No such file or directory!")
    sys.exit(1)

# Read corner names from the file
with open(filename, "r") as file:
    cor_dir = [line.strip() for line in file]

# Process each corner
for cor in cor_dir:
    try:
        # Open the base input.scs file
        if not os.path.exists("input.scs"):
            print("input.scs: No such file or directory!")
            sys.exit(1)

        with open("input.scs", "r") as rdf:
            base_lines = rdf.readlines()

        # Create a directory for the corner and navigate into it
        os.makedirs(cor, exist_ok=True)
        os.chdir(cor)

        # Parse the corner name
        par_corn = cor.split('_')
        prc = par_corn[0]
        prcres = par_corn[1]
        temr = f"temp = {par_corn[2]} \\"
        paras = f"parameters tmp_param ={par_corn[2]}"

        # Build the parameters string
        parameters = paras
        for i in range(3, len(par_corn), 2):
            par_corn_val = par_corn[i + 1].replace("P", ".")
            parameters += f" {par_corn[i]} = {par_corn_val}"

        # Write the corner_def file
        with open("corner_def", "w") as cdef:
            cdef.write("simulator lang = spectre\n")
            process_line = f"include \"/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_180/models/spectre/cr018gpii_v1d0.scs\" section={prc}\n"
            cdef.write(process_line)
            gb = prcres[:2]
            cdef.write(
                f"include \"/data/cad/pdk_all/pdk_tsmc/pdk_tsmc_180/models/spectre/cr018gpii_v1d0.scs\" section={gb}_res\n"
            )
	#include more parameters here if required
            cdef.write(parameters)

        # Generate the generated.scs file
        with open("generated.scs", "w") as wrf:
            for line in base_lines:
                wrf.write(line)
                if "simulator lang=" in line:
                    wrf.write("include \"corner_def\"\n")

        # Remove old simulation data
        if os.path.exists("generated.raw"):
            shutil.rmtree("generated.raw")
        if os.path.exists("run.log"):
            os.remove("run.log")

        # Run Spectre simulation
        cmd = "spectre -64 +l spectre.log +lqt 0 +lqs +lsusp ++aps generated.scs"
        os.system(cmd)

        # Navigate back to the parent directory
        os.chdir("..")

    except Exception as e:
        print(f"Error processing corner {cor}: {e}")
        os.chdir("..")

# At the very end of corner_run_part.py
done_marker = f"{filename}.done"
with open(done_marker, "w") as df:
    df.write("DONE\n")
print(f" Done marker written: {done_marker}")


