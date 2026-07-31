import pandas as pd

jobs = 5
# Define the base file name pattern and output file
base_file_name = 'Result_tran_0{}.out'
output_file = 'combined_results.xlsx'

# Initialize an empty DataFrame to accumulate all the data
all_data = pd.DataFrame()

# Variable to store column names
columns = None

# Loop over the file numbers
for i in range(1, jobs + 1):
    # Construct the file name
    input_file = base_file_name.format(i)

    # Read the text file
    with open(input_file, 'r') as file:
        lines = file.readlines()

    # Extract the header and data
    if i == 1:
        # First file: take the header and the data
        headers = lines[0].split()
        # Check if the second row has more elements than the headers
        second_row = lines[1].split()
        if len(second_row) > len(headers):
            columns = ['Name'] + headers
        else:
            columns = headers
        rows = [line.split() for line in lines[1:]]
    else:
        # Subsequent files: skip the first line (header)
        rows = [line.split() for line in lines[1:]]

    # Ensure each row has the correct number of columns
    # rows = [row[:len(columns) - 1] + [''] * (len(columns) - len(row) - 1) for row in rows]

    # Create a DataFrame for the current file
    df = pd.DataFrame(rows, columns=columns)

    # Append the DataFrame to the cumulative DataFrame
    all_data = pd.concat([all_data, df], ignore_index=True)

# Save the combined DataFrame to an Excel file
all_data.to_excel(output_file, index=False)

print(f'Data from all files successfully written to {output_file}')

