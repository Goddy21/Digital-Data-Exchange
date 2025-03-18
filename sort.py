import os
import pandas as pd
import tkinter as tk
from tkinter import filedialog, messagebox
import datetime

# Get desktop path and create SORT RESULT folder
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
sort_result_folder = os.path.join(desktop_path, "SORT RESULT")

if not os.path.exists(sort_result_folder):
    os.makedirs(sort_result_folder)


def select_folder():
    folder_path = filedialog.askdirectory()
    folder_var.set(folder_path)


def execute_filter():
    folder = folder_var.get()
    search_name = search_name_var.get().strip().lower()
    output_file = os.path.join(sort_result_folder, f"{search_name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")

    # DataFrame to store all filtered results for the search term
    filtered_data = pd.DataFrame(columns=['Credit Identity String', 'Customer Name'])

    # Define required columns
    required_columns = ['Credit Identity String', 'Customer Name']

    try:
        # Iterate over each file in the specified directory
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)

            # Handle Excel files
            if filename.endswith('.xlsx') or filename.endswith('.xlsm'):
                xls = pd.ExcelFile(filepath)

                for sheet_name in xls.sheet_names:
                    df = xls.parse(sheet_name)
                    print(f"Checking file: {filename}, sheet: {sheet_name}")

                    # Normalize column names by stripping whitespace
                    df.columns = df.columns.str.strip()

                    # Debugging: Print available columns
                    print(f"Columns in {filename}, sheet {sheet_name}: {df.columns.tolist()}")

                    # Check for the required columns
                    actual_columns = df.columns.str.strip().str.lower()

                    if all(col.lower() in actual_columns for col in required_columns):
                        # Filter rows based on the search_name in 'Customer Name' column
                        filtered_rows = df[df['Customer Name'].str.contains(search_name, case=False, na=False)]
                        print(f"Number of filtered rows for '{search_name}': {len(filtered_rows)}")

                        if not filtered_rows.empty:
                            available_columns = [col for col in ['Credit Identity String', 'Customer Name'] if col in df.columns]
                            filtered_data = pd.concat([filtered_data, filtered_rows[available_columns]], ignore_index=True)
                    else:
                        missing_cols = set(required_columns) - set(actual_columns)
                        print(f"Required columns not found in {filename} - {sheet_name}: {missing_cols}")
                        print("First few rows of the DataFrame:")
                        print(df.head())

            # Handle CSV files
            elif filename.endswith('.csv'):
                try:
                    df = pd.read_csv(filepath, header=0, on_bad_lines='skip')
                    print(f"Checking file: {filename} (CSV)")

                    df.columns = df.columns.str.strip()

                    print(f"Columns in {filename} (CSV): {df.columns.tolist()}")

                    actual_columns = df.columns.str.strip().str.lower()

                    if all(col.lower() in actual_columns for col in required_columns):
                        filtered_rows = df[df['Customer Name'].str.contains(search_name, case=False, na=False)]
                        print(f"Number of filtered rows for '{search_name}': {len(filtered_rows)}")

                        if not filtered_rows.empty:
                            available_columns = [col for col in ['Credit Identity String', 'Customer Name'] if col in df.columns]
                            filtered_data = pd.concat([filtered_data, filtered_rows[available_columns]], ignore_index=True)
                    else:
                        missing_cols = set(required_columns) - set(actual_columns)
                        print(f"Required columns not found in {filename} (CSV): {missing_cols}")
                        print("First few rows of the DataFrame:")
                        print(df.head())

                except pd.errors.ParserError as e:
                    print(f"Error parsing {filename}: {e}")

        # Save the filtered data for the specific search term in SORT RESULT folder
        if not filtered_data.empty:
            filtered_data.to_excel(output_file, index=False)
            messagebox.showinfo("Success", f"Filtered results for '{search_name}' saved to '{output_file}'.")
        else:
            messagebox.showwarning("No Results", f"No results found for '{search_name}'.")

    except Exception as e:
        messagebox.showerror("Error", str(e))

# Create the main application window
root = tk.Tk()
root.title("Excel Filter Application")

# Define StringVar for folder path and search name
folder_var = tk.StringVar()
search_name_var = tk.StringVar()

# Create UI elements
tk.Label(root, text="Select Folder:").pack(pady=5)
tk.Entry(root, textvariable=folder_var, width=50).pack(pady=5)
tk.Button(root, text="Browse", command=select_folder).pack(pady=5)

tk.Label(root, text="Search Name:").pack(pady=5)
tk.Entry(root, textvariable=search_name_var).pack(pady=5)

tk.Button(root, text="Execute Filter", command=execute_filter).pack(pady=20)

# Run the application
root.mainloop()
