import os
import time
import hashlib
import random
import shutil  # Import shutil for file movement
from ftplib import FTP
import pandas as pd
import xml.etree.ElementTree as ET
from mutagen.mp3 import MP3
from PIL import Image

# Configuration
FTP_SERVER = 'ddex-upload.boomplaymusic.com'
FTP_USERNAME = 'mkononi'
FTP_PASSWORD = 'xIp6jRnQwtNMr6R3'
LOCAL_DIR = r'C:\Goddie\THE SURVIVORS GOSPEL CHOIR'
EXCEL_FILE = os.path.join(LOCAL_DIR, 'choir.xlsx')
BATCH_NUMBER = time.strftime('%Y%m%d')
BATCH_FOLDER = os.path.join(LOCAL_DIR, f"BATCH_{BATCH_NUMBER}")
os.makedirs(BATCH_FOLDER, exist_ok=True)
LOG_FILE = os.path.join(LOCAL_DIR, f"upload_log_{BATCH_NUMBER}.txt")

def read_excel(file_path):
    df = pd.read_excel(file_path, engine='openpyxl')
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
    df.fillna({'primary_artists': 'UNKNOWN_ARTIST', 'label': 'UNKNOWN_LABEL', 'isrc_code': 'UNKNOWN_ISRC', 'upc_code': 'UNKNOWN_UPC'}, inplace=True)
    df['upc_code'] = df['upc_code'].astype(str)
    df['isrc_code'] = df['isrc_code'].astype(str)
    df['duration'] = df['duration'].astype(str)  
    return df

def validate_image_size(image_path):
    with Image.open(image_path) as img:
        if img.width < 800 or img.height < 800:
            print(f"⚠️ Image {image_path} is too small ({img.width}x{img.height}). Skipping upload.")
            return False
    return True

def format_duration(duration):
    try:
        parts = duration.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return f"PT{hours}H{minutes}M{seconds}S" if hours > 0 else f"PT{minutes}M{seconds}S"
        elif len(parts) == 2:
            minutes, seconds = map(int, parts)
            return f"PT{minutes}M{seconds}S"
    except:
        return 'PT0M0S'

def move_to_batch_folder(file_path, upc_code):
    """Move a file to its corresponding UPC folder in the batch directory."""
    resource_folder = os.path.join(BATCH_FOLDER, upc_code)
    os.makedirs(resource_folder, exist_ok=True)

    if os.path.exists(file_path):
        dest_path = os.path.join(resource_folder, os.path.basename(file_path))
        shutil.copy2(file_path, dest_path)  # Copy file with metadata
        return dest_path  # Return new location
    return None

def generate_md5(file_path):
    if not os.path.exists(file_path):
        return 'MISSING_FILE'
    hash_md5 = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def create_ddex_xml(row):
    resource_folder = os.path.join(BATCH_FOLDER, row['upc_code'])
    os.makedirs(resource_folder, exist_ok=True)
    
    root = ET.Element('ern:NewReleaseMessage', attrib={
        'xmlns:ern': 'http://ddex.net/xml/ern/383',
        'xmlns:xs': 'http://www.w3.org/2001/XMLSchema-instance',
        'LanguageAndScriptCode': 'en',
        'MessageSchemaVersionId': 'ern/383'
    })
    
    header = ET.SubElement(root, 'MessageHeader')
    ET.SubElement(header, 'MessageThreadId').text = f"{random.randint(100000, 999999)}-{random.randint(1000, 9999)}"
    ET.SubElement(header, 'MessageId').text = f"{random.randint(100000, 999999)}-{random.randint(1000, 9999)}"
    ET.SubElement(header, 'MessageCreatedDateTime').text = time.strftime('%Y-%m-%dT%H:%M:%S+00:00')
    ET.SubElement(header, 'MessageControlType').text = 'LiveMessage'
    
    ET.SubElement(root, 'UpdateIndicator').text = 'OriginalMessage'
    
    resource_list = ET.SubElement(root, 'ResourceList')
    sound_recording = ET.SubElement(resource_list, 'SoundRecording')
    ET.SubElement(sound_recording, 'SoundRecordingType').text = 'MusicalWorkSoundRecording'
    sound_id = ET.SubElement(sound_recording, 'SoundRecordingId')
    ET.SubElement(sound_id, 'ISRC').text = row['isrc_code']
    ET.SubElement(sound_recording, 'ResourceReference').text = 'A1'
    ET.SubElement(sound_recording, 'ReferenceTitle').text = row['track_titles']
    
    details = ET.SubElement(sound_recording, 'SoundRecordingDetailsByTerritory')
    ET.SubElement(details, 'TerritoryCode').text = 'Worldwide'
    ET.SubElement(details, 'Duration').text = 'PT5M2S'
    ET.SubElement(details, 'AudioCodecType').text = 'MP3'
    
    image = ET.SubElement(resource_list, 'Image')
    ET.SubElement(image, 'ImageType').text = 'FrontCoverImage'
    ET.SubElement(image, 'ResourceReference').text = 'A2'
    
    release_list = ET.SubElement(root, 'ReleaseList')
    release = ET.SubElement(release_list, 'Release')
    release_id = ET.SubElement(release, 'ReleaseId')
    ET.SubElement(release_id, 'GRid').text = 'A10302B0005982538V'
    ET.SubElement(release_id, 'ICPN').text = row['upc_code']
    ET.SubElement(release, 'ReleaseReference').text = 'R0'
    ET.SubElement(release, 'ReferenceTitle').text = row['track_titles']
    
    display_artist = ET.SubElement(release, 'DisplayArtist')
    artist_name = ET.SubElement(display_artist, 'PartyName')
    ET.SubElement(artist_name, 'FullName').text = row.get('primary_artists', 'UNKNOWN_ARTIST')
    ET.SubElement(display_artist, 'ArtistRole').text = 'MainArtist'
    
    release_ref_list = ET.SubElement(release, 'ReleaseResourceReferenceList')
    ET.SubElement(release_ref_list, 'ReleaseResourceReference', attrib={'ReleaseResourceType': 'PrimaryResource'}).text = 'A1'
    ET.SubElement(release_ref_list, 'ReleaseResourceReference', attrib={'ReleaseResourceType': 'SecondaryResource'}).text = 'A2'
    
    ET.SubElement(release, 'ParentalWarningType').text = 'NoAdviceAvailable'
    
    genre = ET.SubElement(release, 'Genre')
    ET.SubElement(genre, 'GenreText').text = 'Gospel'
    ET.SubElement(genre, 'SubGenre').text = 'Christian'
    
    p_line = ET.SubElement(release, 'PLine')
    ET.SubElement(p_line, 'Year').text = '2024'
    ET.SubElement(p_line, 'PLineText').text = f'℗ 2024 {row.get("label", "UNKNOWN_LABEL")}'
    
    c_line = ET.SubElement(release, 'CLine')
    ET.SubElement(c_line, 'Year').text = '2024'
    ET.SubElement(c_line, 'CLineText').text = f'© 2024 {row.get("primary_artists", "UNKNOWN_ARTIST")}'
    
    xml_filename = os.path.join(resource_folder, f"{row['track_titles'].replace(' ', '_')}_update.xml")
    ET.ElementTree(root).write(xml_filename, encoding='utf-8', xml_declaration=True)
    return xml_filename


def ensure_ftp_directory(ftp, directory):
    """Ensure the directory exists on the FTP server, create if missing."""
    try:
        ftp.cwd(directory)
    except Exception:
        try:
            ftp.mkd(directory)
            ftp.cwd(directory)
        except Exception as e:
            print(f"❌ Failed to create FTP directory {directory}: {e}")


def upload_to_ftp(file_path, upc_code):
    """Upload a file to the FTP server, ensuring it goes into the correct batch and UPC folder."""
    try:
        with FTP(FTP_SERVER) as ftp:
            ftp.login(FTP_USERNAME, FTP_PASSWORD)
            batch_dir = f"/BATCH_{BATCH_NUMBER}"
            upc_dir = f"{batch_dir}/{upc_code}"

            ensure_ftp_directory(ftp, batch_dir)
            ensure_ftp_directory(ftp, upc_dir)

            filename = os.path.basename(file_path)
            if filename in ftp.nlst():
                print(f"🔄 Skipping duplicate: {file_path}")
                return

            with open(file_path, 'rb') as file:
                ftp.storbinary(f"STOR {filename}", file)
            print(f"✅ Uploaded: {file_path}")
    except Exception as e:
        print(f"❌ FTP upload failed for {file_path}: {e}")



def process_and_upload():
    df = read_excel(EXCEL_FILE)
    files_to_upload = []
    
    for _, row in df.iterrows():
        print(f"📝 Processing track: {row['track_titles']} (ISRC: {row['isrc_code']}, UPC: {row['upc_code']})")
        upc_code = row['upc_code']
        resource_folder = os.path.join(BATCH_FOLDER, upc_code)
        os.makedirs(resource_folder, exist_ok=True)
        
        for ext, folder in [('mp3', 'AUDIO'), ('wav', 'WAV'), ('jpg', 'IMAGES')]:  
            search_folder = os.path.join(LOCAL_DIR, folder)
            matching_files = [f for f in os.listdir(search_folder) if row['track_titles'].lower().replace(' ', '_') in f.lower() and f.endswith(ext)]
            
            if matching_files:
                file_path = os.path.join(search_folder, matching_files[0])
                if ext == 'jpg' and not validate_image_size(file_path):
                    continue
                new_path = move_to_batch_folder(file_path, upc_code)
                if new_path:
                    files_to_upload.append((new_path, upc_code))
            else:
                with open(LOG_FILE, 'a') as log:
                    log.write(f"Missing file: {row['track_titles']}.{ext}\n")
        
        xml_file = create_ddex_xml(row)
        if xml_file:
            files_to_upload.append((xml_file, upc_code))
    
    print("📝 Files ready for upload:")
    for file, _ in files_to_upload:
        print(file)
    
    confirm = input("❓ Proceed with upload? (y/n): ")
    if confirm.lower() == 'y':
        for file, upc_code in files_to_upload:
            upload_to_ftp(file, upc_code)
    
if __name__ == '__main__':
    print("🚀 Starting process...")
    process_and_upload()
    print("✅ All done!")

