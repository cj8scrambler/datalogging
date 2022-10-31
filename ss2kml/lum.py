from __future__ import print_function
import pickle
import os.path
import re
import sys, getopt
import googlemaps
import simplekml
from datetime import date
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Google Sheets permissions
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

# Google Sheets source data
# Original 2021 sign up sheet
DOCUMENT_ID = 'XXXXX_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

# Tabs to itterate over in Google Sheet.  These are hardcode
# because I couldn't figure this out dynamicly.
SHEETS=['BEYE ZONE', 'HATCH ZONE', 'HOLMES ZONE', 'IRVING ZONE',
        'LINCOLN ZONE', 'LONGFELLOW ZONE', 'MANN ZONE', 'WHITTIER ZONE',
        'FOREST PARK ZONE', 'RIVER FOREST', 'GALEWOOD ZONE']

# Google APIs key from https://console.developers.google.com/
# This is a personal key which can cost money if there is a large volume
# of requests.  In my use, I haven't hit any charges yet.
# The key needs these APIs enabled:
#   Geocoding
#   Roads
#   Google Sheets
G_KEY='XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'

# Regular Expression pattern for matching data in spreadsheet
RE_PATTERN='^([0-9]+)\s*(.*)$'

def street_loc(number, location_string):
    """Take the given location address and location string, returns a
       dictionary of the middle of the street closest to the address
       Example:  street_loc(1060, 'W. Addison, Chicago IL')
    """
    gmaps = googlemaps.Client(key=G_KEY)
    locstring = str(number + 0) + ' ' + location_string 
    loc1 = gmaps.geocode(locstring)
    #print("  1: %s: %s" % (locstring, loc1[0]['geometry']['location']))

    locstring = str(number + 1) + ' ' + location_string 
    loc2 = gmaps.geocode(locstring)
    #print("  2: %s: %s" % (locstring, loc2[0]['geometry']['location']))

    middle_lat = (float(loc1[0]['geometry']['location']['lat']) +
                  float(loc2[0]['geometry']['location']['lat'])) / 2.0 
    middle_long = (float(loc1[0]['geometry']['location']['lng']) +
                   float(loc2[0]['geometry']['location']['lng'])) / 2.0 
    point = {'latitude': middle_lat, 'longitude': middle_long}
    print("    R: %s" % (point))
    return point

def main(only_count):
    """Fetch data from 1st column of Google Sheet, parse it as block
       addresses, generate a KML file with lines representing those blocks
    """

    # Establish Google sheets authorization credentials
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, have the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("Create a 'credentials.json' file which contains your " +
                        "OAuth client ID and secret.  For more details, see:")
                print("https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred")
                return
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    # Setup the services
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()
    gmaps = googlemaps.Client(key=G_KEY)
    kml = simplekml.Kml(open=1)

    total = 0
    for tab in SHEETS:
        # Get Column A from each tab
        result = sheet.values().get(spreadsheetId=DOCUMENT_ID, range=tab+'!A1:B99').execute()
        values = result.get('values', [])

        print('Spreadsheet tab: %s' % (tab))
        if not values:
            print('No data found');
        else:
            for row in values:
                # Skip the empty cells
                if not len(row):
                    continue

                # Expected column data:
                #   row[0] Block name
                #   row[1] Block captain
                #   row[2] Captain email
                #   row[3] Captain cell

                # Use a regexp to extract the block number and the rest of the address
                match = re.search(RE_PATTERN, row[0])
                if match:
                    city = "Oak Park, IL"
                    if 'FOREST PARK' in tab:
                        city = "Forest Park, IL"
                    if 'RIVER FOREST' in tab:
                        city = "River Forest, IL"
                    if 'GALEWOOD' in tab:
                        city = "Chicago, IL"

                    total += 1

                    print ("%s %s (%d)" % (match.group(1), match.group(2), len(row)))

                    if only_count:
                        continue

                    # 400 S. Grove doesn't resolve correctly (use 401 instead)
                    if ('S Grove' in match.group(2) or 'S. Grove' in match.group(2)) and (400 == int(match.group(1))):
                        first_address = 401
                    else:
                        first_address = int(match.group(1))

                    print ("  {} {}, {}".format(first_address, match.group(2), city))
                    startpoint = street_loc(first_address, "{}, {}".format(match.group(2), city))

                    # Take a guess at an address that represents the end of the block.
                    # Most blocks go up to about 45.  A few blocks start at 50 and go
                    # up to 99 (far south end of OP).  But the eastern blocks need to
                    # go over 50 to get to the end.
                    if 'Cuyler' in match.group(2):
                        last_address = int(match.group(1))+98
                    elif 'N Harvey' in match.group(2) or 'N. Harvey' in match.group(2):
                        last_address = int(match.group(1))+98
                    elif 'N Lombard' in match.group(2) or 'N. Lombard' in match.group(2):
                        last_address = int(match.group(1))+98
                    elif 'N Taylor' in match.group(2) or 'N. Taylor' in match.group(2):
                        last_address = int(match.group(1))+98
                    elif 'Hayes' in match.group(2):
                        last_address = int(match.group(1))+98
                    elif 'N Humphrey' in match.group(2) or 'N. Humphrey' in match.group(2):
                        last_address = int(match.group(1))+98
                    elif 'Lathrop' in match.group(2):
                        last_address = int(match.group(1))+98
#                    elif 'S Humphrey' in match.group(2) or 'S. Humphrey' in match.group(2):
#                        # 500 S. Humphrey has to end with 44/45 (not 48/49)
#                        if '1100' in match.group(1):
#                            last_address = int(match.group(1))+44
                    else:
#                        last_address = int(match.group(1))+48
                        last_address = int(match.group(1))+44

                    print ("  {} {}, {}".format(last_address, match.group(2), city))
                    endpoint = street_loc(last_address, "{}, {}".format(match.group(2), city))

                    # Take the location and snap it to the nearest road
                    street = gmaps.nearest_roads([startpoint, endpoint])
                    points = []
                    for l in street:
                        point = ( l['location']['longitude'], l['location']['latitude'] )
                        points.append(point)

                    # Draw a thick red line on that road segment
                    if (len(row) >= 2):
                        line = kml.newlinestring(name=row[0],
                                                 description="Organzed by {}".format(row[1]),
                                                 coords=points)
                    else:
                        line = kml.newlinestring(name=row[0], coords=points)
                    line.style.linestyle.color = 'ff0000ff'
                    line.style.linestyle.width = 10
                else:
                    if 'ZONE' not in row[0]:
                        print("Could not parse: %s" % (row[0]))
        print("")

    if only_count:
        print("Counted %d participating blocks" % (total));
    else:
        kmlfile = 'Participating Blocks - ' + str(total) + ' as of '
        kmlfile += date.today().strftime("%b %d") +'.kml'
        kml.save(kmlfile)
        print("Saved data to: %s" % (kmlfile))

if __name__ == '__main__':
    justcount = 0;

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hl")
    except getopt.GetoptError:
        print ('lum.py [-h] [-l]')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print ('lum.py [-h] [-l]')
            sys.exit()
        elif opt == '-l':
            justcount=1

    main(justcount)
