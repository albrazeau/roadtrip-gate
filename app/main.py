from flask import Flask, render_template, request, jsonify, Markup
from pipeline import get_geotagging, get_labeled_exif, get_exif, get_decimal_from_dms, get_coordinates, clean_img, insert_pg
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import folium
from folium import IFrame
import base64
import glob
import os
import psycopg2

app = Flask(__name__)

raw_img_dir = "/data/raw"
clean_dir = "/data/ready"

# conn = psycopg2.connect(host={}, 
#                         port={}, 
#                         database={}, 
#                         user="postgres", 
#                         password="postgres").format(
#     os.environ["DBHOST"], os.environ["DBUSER"], os.environ["DBPASS"], os.environ["DBNAME"], os.environ["DBPORT"]
# )

DB_CONNECTION = "host={} user={} password={} dbname={} port={}".format(
    os.environ["DBHOST"], os.environ["DBUSER"], os.environ["DBPASS"], os.environ["DBNAME"], os.environ["DBPORT"]
)

# images = list(set(glob(os.path.join(raw_img_dir, "*.JPG")) + glob(os.path.join(raw_img_dir, "*.jpg"))))

@app.context_processor
def my_utility_processor():

    def create_map():
        
        img = '/data/raw/IMG_0693.JPG'

        UScenter = ('37.809734', '-97.555620')

        exif = get_exif(img)
        geotags = get_geotagging(exif)
        lat, lon = get_coordinates(geotags)

        image = Image.open(img)
        image = image.resize((225,int(225*1.33)), Image.ANTIALIAS)
        image.save('test.JPG', quality=100)
        
        encoded = base64.b64encode(open('test.JPG', 'rb').read())
        html = '<img src="data:image/JPG;base64,{}">'.format
        iframe = IFrame(html(encoded.decode("UTF-8")), width=225+20, height=300+20)
        popup = folium.Popup(iframe, max_width=250)
        tooltip = "Phelps Lake, Grand Teton National Park"
        
        folium_map = folium.Map(location=UScenter, 
                    zoom_start=5, scrollWheelZoom=False,  
                    tiles="Stamen Terrain")

        folium.Marker(location=(lat, lon), tooltip=tooltip, popup=popup, icon=folium.Icon(color='blue')).add_to(folium_map)

        return Markup(folium_map._repr_html_())

    return dict(create_map=create_map)

@app.route("/")
def home():

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
