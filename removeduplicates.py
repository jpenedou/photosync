import re
import subprocess

# Define the paths to search
search_path = '/mnt/d/fotos'
input_file_path = './duplicadosinput'
find_output_path = './duplicadosfindoutput'
output_file_path = './duplicadosoutput'

# Search for the file path in each line of the log file
file_paths = []
found_paths = []

# Define the pattern for the file path in the log
path_pattern = r'\./.*\..*'
delete_pattern = f'{search_path}.*'

# Open the input file containing the list of file paths
with open(input_file_path, 'r') as input_file:
    # Read in the lines of the input file
    paths = input_file.readlines()
    
    for line in paths:
        # Use regular expressions to search for the file path in the line
        match = re.search(path_pattern, line)
        if match:
            # If a match is found, add the file path to the list of file paths
            file_paths.append(match.group())

with open(find_output_path, 'w') as find_output_file:
    # Iterate over the file paths and run the find command for each path
    for path in file_paths:
        # Remove the first two characters from the path
        path = path[2:]
        path = path.replace('.', '*')

        # Construct the find command
        find_command = f'find {search_path} -name \"{path}\" -printf "%s %p\\n"'
        # find_command = ['find', search_path, '-name', f'"{path}"']

        print(find_command)

        # Run the find command and capture the output
        result = subprocess.run([find_command], stdout=find_output_file, text=True, shell=True)


with open(find_output_path, 'r') as find_output_file:
    # Read in the lines of the input file
    paths = find_output_file.readlines()
    
    for line in paths:
        # Use regular expressions to search for the file path in the line
        # found_paths = re.search(path_pattern, line)
        found_paths.append(line.replace('_d.', '.'))

# Find the paths that appear more than once (i.e., are duplicates)
duplicate_paths = set(path for path in found_paths if found_paths.count(path) > 1)

# Open the output file to write the duplicate paths to
with open(output_file_path, 'w') as output_file:
    # Write the duplicate paths to the output file
    output_file.writelines(duplicate_paths)
    
# Print the list of file paths
print(duplicate_paths)


# # Eliminar ficheros
# with open(output_file_path, 'r') as input_file:
#     # Read in the lines of the input file
#     paths = input_file.readlines()
    
#     for line in paths:
#         # Use regular expressions to search for the file path in the line
#         match = re.search(delete_pattern, line)
#         if match:
#             # If a match is found, add the file path to the list of file paths
#             # file_paths.append(match.group())
#             print(match.group())
#             delete_command = f'rm {match.group()}'
#             result = subprocess.run([delete_command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
#             print(result.stdout)