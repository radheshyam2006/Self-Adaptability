#!/bin/bash
# Auto-generated PVT corner sweep script
# Run this on the IIIT server after uploading all dummy_sensors_*.v files

RTL_IMPORT="/data/proj/Low_power_design/tech_tsmc128nm/work/users/user13/rtl_import"
RESULTS_FILE="$HOME/sweep_results.csv"

# CSV header
echo "corner_idx,corner_name,vreg,temperature,pmon,status" > $RESULTS_FILE

echo ""
echo "================================================================"
echo "  Corner 1/5: tt_vdd_temp_0"
echo "  vreg=0.81V, temp=-40.0C"
echo "================================================================"

# Copy the dummy_sensors for this corner
cp $RTL_IMPORT/dummy_sensors_1.v $RTL_IMPORT/dummy_sensors.v
echo "Copied dummy_sensors_1.v -> dummy_sensors.v"

# Record that this corner is ready
echo "1,tt_vdd_temp_0,0.81,-40.0,248568380.0,ready" >> $RESULTS_FILE

echo ">>> NOW: In Maestro CIW, type: desVar(\"vreg\" 0.81)"
echo ">>> THEN: Click Recreate Netlist -> Run"
echo ">>> Press ENTER here when simulation is done..."
read -p ""

echo ""
echo "================================================================"
echo "  Corner 2/5: tt_vdd_temp_1"
echo "  vreg=0.81V, temp=-39.5C"
echo "================================================================"

# Copy the dummy_sensors for this corner
cp $RTL_IMPORT/dummy_sensors_2.v $RTL_IMPORT/dummy_sensors.v
echo "Copied dummy_sensors_2.v -> dummy_sensors.v"

# Record that this corner is ready
echo "2,tt_vdd_temp_1,0.81,-39.5,248491330.0,ready" >> $RESULTS_FILE

echo ">>> NOW: In Maestro CIW, type: desVar(\"vreg\" 0.81)"
echo ">>> THEN: Click Recreate Netlist -> Run"
echo ">>> Press ENTER here when simulation is done..."
read -p ""

echo ""
echo "================================================================"
echo "  Corner 3/5: tt_vdd_temp_2662"
echo "  vreg=0.97V, temp=-29.0C"
echo "================================================================"

# Copy the dummy_sensors for this corner
cp $RTL_IMPORT/dummy_sensors_3.v $RTL_IMPORT/dummy_sensors.v
echo "Copied dummy_sensors_3.v -> dummy_sensors.v"

# Record that this corner is ready
echo "3,tt_vdd_temp_2662,0.97,-29.0,369419010.0,ready" >> $RESULTS_FILE

echo ">>> NOW: In Maestro CIW, type: desVar(\"vreg\" 0.97)"
echo ">>> THEN: Click Recreate Netlist -> Run"
echo ">>> Press ENTER here when simulation is done..."
read -p ""

echo ""
echo "================================================================"
echo "  Corner 4/5: tt_vdd_temp_10"
echo "  vreg=0.81V, temp=-35.0C"
echo "================================================================"

# Copy the dummy_sensors for this corner
cp $RTL_IMPORT/dummy_sensors_4.v $RTL_IMPORT/dummy_sensors.v
echo "Copied dummy_sensors_4.v -> dummy_sensors.v"

# Record that this corner is ready
echo "4,tt_vdd_temp_10,0.81,-35.0,247770450.0,ready" >> $RESULTS_FILE

echo ">>> NOW: In Maestro CIW, type: desVar(\"vreg\" 0.81)"
echo ">>> THEN: Click Recreate Netlist -> Run"
echo ">>> Press ENTER here when simulation is done..."
read -p ""

echo ""
echo "================================================================"
echo "  Corner 5/5: tt_vdd_temp_3295"
echo "  vreg=0.99V, temp=123.0C"
echo "================================================================"

# Copy the dummy_sensors for this corner
cp $RTL_IMPORT/dummy_sensors_5.v $RTL_IMPORT/dummy_sensors.v
echo "Copied dummy_sensors_5.v -> dummy_sensors.v"

# Record that this corner is ready
echo "5,tt_vdd_temp_3295,0.99,123.0,326279260.0,ready" >> $RESULTS_FILE

echo ">>> NOW: In Maestro CIW, type: desVar(\"vreg\" 0.99)"
echo ">>> THEN: Click Recreate Netlist -> Run"
echo ">>> Press ENTER here when simulation is done..."
read -p ""

echo ""
echo "All corners complete! Results logged to $RESULTS_FILE"
echo "Now record your pup/pdown values in the results file."