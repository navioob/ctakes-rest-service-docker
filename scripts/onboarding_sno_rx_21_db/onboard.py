import os

def split_file_by_rows(input_filepath, output_dir, max_rows_per_file=20000):
    """
    Splits a large text file (like a .script or .sql) into smaller files
    based on a maximum number of rows per file.

    Args:
        input_filepath (str): The path to the large input file.
        output_dir (str): The directory to save the output files.
        max_rows_per_file (int): The maximum number of lines (rows) in each output file.
    """
    
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Base name for the output files (e.g., 'load' from '02_load.sql')
    output_filename_base = "load"
    
    # Initialize counters
    file_counter = 2  # Start from 2 as per the requirement (02_load.sql, 03_load.sql, ...)
    row_counter = 0
    current_output_file = None

    try:
        # Open the input file for reading
        with open(input_filepath, 'r') as infile:
            print(f"Starting to read from {input_filepath}...")
            
            # Read lines one by one
            for line in infile:
                if row_counter == 0:
                    # Time to start a new output file

                    # Close the previous file if it exists
                    if current_output_file:
                        current_output_file.close()

                    # Determine the new file name (e.g., 001_load.sql, 002_load.sql)
                    # Using a 3-digit zero-padded counter
                    file_number_str = str(file_counter).zfill(2)
                    output_filename = f"{file_number_str}_{output_filename_base}.sql"
                    output_path = os.path.join(output_dir, output_filename)
                    
                    # Open the new output file
                    current_output_file = open(output_path, 'w')
                    current_output_file.write("use umls;\n")
                    print(f"Created new file: {output_filename}")
                    file_counter += 1

                # Write the line to the current output file
                current_output_file.write(line.replace('\n', ';') + '\n')
                row_counter += 1

                # Reset row counter if the limit is reached
                if row_counter >= max_rows_per_file:
                    row_counter = 0

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Ensure the last output file is closed
        if current_output_file:
            current_output_file.close()

    print("File splitting complete.")

# --- Configuration ---
INPUT_FILE = './snorx_2021aa.script'  # <-- **CHANGE THIS to your input file name**
OUTPUT_DIRECTORY = '../../sno_rx_21_aa_db' # <-- **CHANGE THIS to your desired output folder**
MAX_ROWS = 50000

# Run the function
split_file_by_rows(INPUT_FILE, OUTPUT_DIRECTORY, MAX_ROWS)