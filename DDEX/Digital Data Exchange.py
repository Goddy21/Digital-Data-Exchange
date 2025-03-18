import os
import time
import hashlib
import random
from ftplib import FTP
import pandas as pd
import xml.etree.ElementTree as ET
from mutagen.mp3 import MP3
from PIL import Image

# Configuration
FTP_SERVER = 'ddex-upload.boomplaymusic.com'
FTP_USERNAME = 'mkononi'
FTP_PASSWORD = 'xIp6jRnQwtNMr6R3'
REMOTE_DIR = '/'
#REMOTE_DIR = f"/BATCH_{BATCH_NUMBER}/"
LOCAL_DIR = r'C:\Goddie\THE SURVIVORS GOSPEL CHOIR'
EXCEL_FILE = os.path.join(LOCAL_DIR, 'choir.xlsx')
BATCH_NUMBER = '20250306'
BATCH_FOLDER = os.path.join(LOCAL_DIR, f"BATCH_{BATCH_NUMBER}")
os.makedirs(BATCH_FOLDER, exist_ok=True)

#resource_folder = os.path.join(BATCH_FOLDER, str(row['upc_code']))
#os.makedirs(resource_folder, exist_ok=True)


# Read and clean Excel data
def read_excel(file_path):
    df = pd.read_excel(file_path, engine='openpyxl')
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
    df = df.dropna(subset=['track_titles'])
    
    df.fillna({'primary_artists': 'UNKNOWN_ARTIST', 'label': 'UNKNOWN_LABEL'}, inplace=True)
    df['physical_release_date'] = pd.to_datetime(df['physical_release_date'], errors='coerce')
    
    df.fillna({'isrc_code': '', 'upc_code': ''}, inplace=True)
    df['upc_code'] = df['upc_code'].astype(str)
    df['isrc_code'] = df['isrc_code'].astype(str)
    df['duration'] = df['duration'].astype(str)  
    
    print("🔍 Duration values from Excel:")
    print(df[['track_titles', 'duration']])
    return df

# Generate MD5 hash for file verification
def generate_md5(file_path):
    if not os.path.exists(file_path):
        return 'MISSING_FILE'
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

# Convert duration format
def format_duration(duration):
    print(f"🕒 Formatting duration: {duration}")
    try:
        parts = duration.split(':')
        
        if len(parts) == 3:  # Possible HH:MM:SS or wrongly formatted MM:SS:00
            hours, minutes, seconds = map(int, parts)
            
            # If hours == 0 or unrealistic (e.g., <6), assume MM:SS format
            if hours == 0 or (hours < 6 and minutes < 60):  
                return f"PT{hours}M{minutes}S"
            return f"PT{hours}H{minutes}M{seconds}S"  # Keep valid HH:MM:SS format

        elif len(parts) == 2:  # Correct MM:SS format
            minutes, seconds = map(int, parts)
            return f"PT{minutes}M{seconds}S"

        else:
            print(f"⚠️ Unexpected duration format: {duration}")
            return 'PT0M0S'
    
    except Exception as e:
        print(f"❌ Failed to format duration: {duration} - {e}")
        return 'PT0M0S'


# Standardize filenames
def standardize_filename(filename):
    return filename.lower().replace(' ', '_')

# Create DDEX XML for each track
def create_ddex_xml(row, track_number):
    # Skip tracks missing ISRC or UPC
    
    if pd.isna(row['isrc_code']) or row['isrc_code'] == 'None':
        print(f"⚠️ Skipping {row['track_titles']} - Missing ISRC Code")
        return None
    if pd.isna(row['upc_code']) or row['upc_code'] == 'None':
        print(f"⚠️ Skipping {row['track_titles']} - Missing UPC Code")
        return None
    """
    if pd.isna(row['isrc_code']) or row['isrc_code'] == 'None':
        print(f"⚠️ Warning: {row['track_titles']} is missing an ISRC Code. Proceeding anyway.")
        row['isrc_code'] = 'UNKNOWN_ISRC'

    if pd.isna(row['upc_code']) or row['upc_code'] == 'None':
        print(f"⚠️ Warning: {row['track_titles']} is missing a UPC Code. Proceeding anyway.")
        row['upc_code'] = 'UNKNOWN_UPC'
    """

    track_title = standardize_filename(row['track_titles'])
    #resource_folder = os.path.join(LOCAL_DIR, str(row['upc_code']))  
    #os.makedirs(resource_folder, exist_ok=True)
    resource_folder = os.path.join(BATCH_FOLDER, str(row['upc_code']))
    os.makedirs(resource_folder, exist_ok=True)


    root = ET.Element('ern:NewReleaseMessage', attrib={
        'xmlns:ern': 'http://ddex.net/xml/ern/383',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xsi:schemaLocation': 'http://ddex.net/xml/ern/383/release-notification.xsd',
        'MessageSchemaVersionId': 'ern/383'
    })

    header = ET.SubElement(root, 'MessageHeader')
    ET.SubElement(header, 'MessageThreadId').text = f"{random.randint(100000, 999999)}-{random.randint(1000, 9999)}"
    ET.SubElement(header, 'MessageId').text = f"{random.randint(100000, 999999)}-{random.randint(1000, 9999)}"
    ET.SubElement(header, 'MessageCreatedDateTime').text = time.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    ET.SubElement(header, 'MessageControlType').text = 'LiveMessage'

    sender = ET.SubElement(header, 'MessageSender')
    ET.SubElement(sender, 'PartyName').text = 'Mkononi Limited'

    recipient = ET.SubElement(header, 'MessageRecipient')
    ET.SubElement(recipient, 'PartyName').text = 'Boomplay Music'
    ET.SubElement(recipient, 'PartyId').text = 'PA-DPIDA-2025021301-D' 

    formatted_duration = format_duration(row.get('duration', '00:00:00'))
    print(f"📝 Final duration for {row['track_titles']}: {formatted_duration}")

    xml_filename = os.path.join(resource_folder, f"{track_title}_update.xml")
    tree = ET.ElementTree(root)
    tree.write(xml_filename, encoding='utf-8', xml_declaration=True)
    return xml_filename

# Upload file to FTP
def upload_to_ftp(file_path):
    with FTP(FTP_SERVER) as ftp:
        ftp.login(FTP_USERNAME, FTP_PASSWORD)
        if REMOTE_DIR not in ftp.nlst():
            ftp.mkd(REMOTE_DIR)
        ftp.cwd(REMOTE_DIR)

    try:
        with FTP(FTP_SERVER) as ftp:
            ftp.login(FTP_USERNAME, FTP_PASSWORD)
            ftp.cwd(REMOTE_DIR)

            existing_files = ftp.nlst()
            filename = os.path.basename(file_path)

            if filename in existing_files:
                print(f"🔄 Skipping duplicate: {file_path}")
                return

            with open(file_path, 'rb') as file:
                ftp.storbinary(f"STOR {filename}", file)

            print(f"✅ Uploaded: {file_path}")
    except Exception as e:
        print(f"❌ FTP upload failed for {file_path}: {e}")

        for ext in ['mp3', 'wav', 'jpg']:
            search_folder = os.path.join(LOCAL_DIR, "AUDIO" if ext == "mp3" else "WAV" if ext == "wav" else "IMAGES")
            file_path = find_file(row['track_titles'], search_folder, [ext])
            
            if file_path:
                batch_file_path = os.path.join(resource_folder, os.path.basename(file_path))
                shutil.move(file_path, batch_file_path)  # Move to batch folder
                files_to_upload.append(batch_file_path)



# Process and upload data
def process_and_upload():
    print("🔍 Reading Excel file...") 
    df = read_excel(EXCEL_FILE)
    files_to_upload = set()
    print(f"✅ Excel read successfully. {len(df)} records found.")
    files_to_upload = []

    for track_number, row in df.iterrows():
        print(f"📝 Processing track {track_number + 1}: {row['track_titles']} (ISRC: {row['isrc_code']}, UPC: {row['upc_code']})")

        for ext in ['mp3', 'wav', 'jpg']:  
            search_folder = os.path.join(LOCAL_DIR, "AUDIO" if ext == "mp3" else "WAV" if ext == "wav" else "IMAGES")

            print(f"🔍 Looking for {row['track_titles']}.{ext} in {search_folder}")  # 🔍 Debugging print
            print(f"📂 Files available: {os.listdir(search_folder)}")  # 📂 Show all available files

            # Search for any file containing the track title
            matching_files = [f for f in os.listdir(search_folder) if standardize_filename(row['track_titles']).replace('_', '') in f.lower().replace('_', '').replace(' ', '') and f.endswith(ext)]

            if matching_files:
                file_path = os.path.join(search_folder, matching_files[0]) 
                print(f"✅ Found file: {file_path}")  
                if file_path not in files_to_upload:  
                    files_to_upload.append(file_path)
            else:
                print(f"⚠️ Missing file: {row['track_titles']}.{ext} in {search_folder}")


        xml_file = create_ddex_xml(row, track_number)
        if xml_file:
            files_to_upload.append(xml_file)


        # If file exists in either location, add it to the upload list
        if os.path.exists(file_path):
            if file_path not in files_to_upload and os.path.exists(file_path):
                print(f"✅ Adding file to upload list: {file_path}")
                files_to_upload.append(file_path)
            elif not os.path.exists(file_path):
                print(f"⚠️ Missing file: {file_path}") 




    print("📝 Files ready for upload:")
    for file in files_to_upload:
        print(file)

    confirm = input("❓ Proceed with upload? (y/n): ")
    if confirm.lower() == 'y':
        for file in files_to_upload:
            print(f"📤 Uploading: {file}")
            upload_to_ftp(file)

if __name__ == '__main__':
    print("🚀 Starting process...")
    process_and_upload()
    print("✅ All done!")
