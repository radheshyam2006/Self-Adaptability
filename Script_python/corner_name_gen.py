import csv

# Input and output file paths
input_file = 'input_samples.csv'
#here instead of output file you can also use corner_names.
output_file = 'output.txt'

# Read the input CSV file
with open(input_file, 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    lines = []
    for row in reader:
        # Replace '.' with 'P' and 'E' with 'e' in all the values
        formatted_values = {key: value.replace('.', 'P').replace('E', 'e') for key, value in row.items()}
        corner = formatted_values['corner']
        if(formatted_values['corner'] == '1'):
            corner = 'ss'
        elif(formatted_values['corner'] == '2'):
            corner = 'tt'
        elif(formatted_values['corner'] == '3'):
            corner = 'ff'

        line = (
            f"{corner}_{corner}res_{formatted_values['temperature']}_vdd_{formatted_values['Vdd']}_"
            # f"tt_ttres_{formatted_values['temperature']}_vdd_{formatted_values['Vdd']}_"
            #f"tt_ttres_27_vdd_1.8_"
            f"wd_{formatted_values['Wd']}_wst_{formatted_values['Wst']}_wdt_{formatted_values['Wdt']}_"
            f"wcm1_{formatted_values['Wcm1']}_ws_{formatted_values['Ws']}_"
            f"RM_{formatted_values['Rc']}_cc_{formatted_values['Cc']}"
        )
        lines.append(line)

# Write to the output file
with open(output_file, 'w') as outfile:
    outfile.write("\n".join(lines))

print(f"Output written to {output_file}")
