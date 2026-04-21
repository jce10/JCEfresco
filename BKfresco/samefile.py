def print_diff_lines(file1_path, file2_path):
    try:
        with open(file1_path, 'r') as file1, open(file2_path, 'r') as file2:
            lines1 = file1.readlines()
            lines2 = file2.readlines()

        for i, (line1, line2) in enumerate(zip(lines1, lines2), start=1):
            if line1 != line2:
                print(f"Difference in line {i}:\nFile 1: {line1.strip()}\nFile 2: {line2.strip()}\n")

        if len(lines1) != len(lines2):
            print("Files have different numbers of lines.")

    except FileNotFoundError:
        print("One or both files not found.")

# Example usage
file1_path = '/home/bkelly/Programs/chi_squared_fitting/completed_fits/50Ti/50Tidp_4880_2p32.txt'
file2_path = '/home/bkelly/Programs/fresco/50Ti_4880_2p32_5+.txt'

print_diff_lines(file1_path, file2_path)






