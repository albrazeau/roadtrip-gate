from geopy.geocoders import Nominatim
from headers import GEOPY_USRNAME

def add_geolocation(city_and_state: str) -> tuple:

    geolocator = Nominatim(user_agent=GEOPY_USRNAME)
    location = geolocator.geocode(city_and_state)

    if location:

        geoloc = (location.latitude, location.longitude)
        return geoloc
        
    else:
        return "No location data found."