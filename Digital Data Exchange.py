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
LOCAL_DIR = r'C:\Goddie\THE SURVIVORS GOSPEL CHOIR'
EXCEL_FILE = os.path.join(LOCAL_DIR, 'choir.xlsx')
BATCH_NUMBER = '20250306'

# Read and clean Excel data
def read_excel(file_path):
    df = pd.read_excel(file_path, engine='openpyxl')
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
    df = df.dropna(subset=['track_titles'])
    df.fillna({'primary_artists': 'UNKNOWN_ARTIST', 'label': 'UNKNOWN_LABEL'}, inplace=True)
    df['physical_release_date'] = pd.to_datetime(df['physical_release_date'], errors='coerce')
    df.fillna({'isrc_code': 'MISSING_ISRC', 'upc_code': 'MISSING_UPC',
               'grid_(optional)': 'UNKNOWN_GRID', 'ean_code_(optional)': 'UNKNOWN_EAN'}, inplace=True)
    df['upc_code'] = df['upc_code'].astype(str)
    df['isrc_code'] = df['isrc_code'].astype(str)
    df['duration'] = df['duration'].astype(str)  # Ensure duration is a string
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
        if len(parts) == 3 and int(parts[0]) < 24 and int(parts[1]) < 60:
            minutes, seconds = map(int, parts[:2])
            return f"PT{minutes}M{seconds}S"
        elif len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return f"PT{hours}H{minutes}M{seconds}S"
        elif len(parts) == 2:
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
    track_title = standardize_filename(row['track_titles'])
    xml_folder = os.path.join(LOCAL_DIR, str(row['upc_code']))
    os.makedirs(xml_folder, exist_ok=True)

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
    ET.SubElement(sender, 'PartyName').text = 'The Survivors Gospel Choir'
    ET.SubElement(sender, 'PartyId').text = 'PADPIDA2011101104E'

    recipient = ET.SubElement(header, 'MessageRecipient')
    ET.SubElement(recipient, 'PartyName').text = 'Boomplay Music'
    ET.SubElement(recipient, 'PartyId').text = 'PA-DPIDA-2025021301-D'

    release_details = ET.SubElement(root, 'ReleaseList')
    release = ET.SubElement(release_details, 'Release')
    ET.SubElement(release, 'ReleaseTitle').text = row['release_title'] or 'Unknown Title'
    ET.SubElement(release, 'ReleaseDate').text = row['physical_release_date'].strftime('%Y-%m-%d') if pd.notna(row['physical_release_date']) else 'UNKNOWN_DATE'
    ET.SubElement(release, 'TerritoryCode').text = 'Worldwide'
    ET.SubElement(release, 'Genre').text = row.get('genre', 'Unknown Genre')
    ET.SubElement(release, 'UPC').text = str(row['upc_code'])

    rights_controller = ET.SubElement(release, 'RightsController')
    ET.SubElement(rights_controller, 'PartyName').text = row.get('label', 'UNKNOWN_LABEL')

    territory_details = ET.SubElement(release, 'ReleaseDetailsByTerritory')
    ET.SubElement(territory_details, 'TerritoryCode').text = 'Worldwide'
    ET.SubElement(territory_details, 'LanguageOfPerformance').text = row.get('language_of_performance', 'en')
    formatted_duration = format_duration(row.get('duration', '00:00:00'))
    print(f"📝 Final duration for {row['track_titles']}: {formatted_duration}")
    ET.SubElement(territory_details, 'Duration').text = formatted_duration

    resource_list = ET.SubElement(root, 'ResourceList')
    for file_type, folder, ext in [('Audio', 'AUDIO', 'mp3'), ('Wav', 'WAV', 'wav'), ('Image', 'IMAGES', 'jpg')]:
        file_path = os.path.join(LOCAL_DIR, folder, f"{track_title}.{ext}")
        if os.path.exists(file_path):
            resource = ET.SubElement(resource_list, file_type, attrib={'ResourceReference': f'{file_type[0]}{track_number + 1}'})
            ET.SubElement(resource, f'{file_type}FileName').text = f"resources/{track_title}.{ext}"
            ET.SubElement(resource, 'ReferenceTitle').text = row['track_titles']
            ET.SubElement(resource, 'HashSum').text = generate_md5(file_path)
            if file_type == 'Audio':
                ET.SubElement(resource, 'ISRC').text = row['isrc_code']

    xml_filename = os.path.join(xml_folder, f"{track_title}_update.xml")
    tree = ET.ElementTree(root)
    tree.write(xml_filename, encoding='utf-8', xml_declaration=True)
    return xml_filename

# List directories on FTP server
def list_ftp_directories():
    try:
        with FTP(FTP_SERVER) as ftp:
            ftp.login(FTP_USERNAME, FTP_PASSWORD)
            ftp.cwd('/')
            directories = ftp.nlst()
            print("📂 Available directories on FTP server:")
            for directory in directories:
                print(directory)
    except Exception as e:
        print(f"❌ Failed to list directories: {e}")

# Upload file to FTP
def upload_to_ftp(file_path):
    try:
        with FTP(FTP_SERVER) as ftp:
            ftp.login(FTP_USERNAME, FTP_PASSWORD)
            ftp.cwd(REMOTE_DIR)
            with open(file_path, 'rb') as file:
                ftp.storbinary(f"STOR {os.path.basename(file_path)}", file)
            print(f"✅ Uploaded: {file_path}")
    except Exception as e:
        print(f"❌ FTP upload failed for {file_path}: {e}")


# Process and upload data
def process_and_upload():
    print("🔍 Reading Excel file...") 
    df = read_excel(EXCEL_FILE)
    print(f"✅ Excel read successfully. {len(df)} records found.")
    files_to_upload = []
    for track_number, row in df.iterrows():
        print(f"📝 Processing track {track_number + 1}: {row['track_titles']}")
        xml_file = create_ddex_xml(row, track_number)
        if xml_file:
            files_to_upload.append(xml_file)
            for folder, ext in [('AUDIO', 'mp3'), ('WAV', 'wav'), ('IMAGES', 'jpg')]:
                file_path = os.path.join(LOCAL_DIR, folder, f"{standardize_filename(row['track_titles'])}.{ext}")
                if os.path.exists(file_path):
                    files_to_upload.append(file_path)
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
    print("🚀 Checking FTP directories...")
    list_ftp_directories()
    process_and_upload()
    print("✅ All done!")
