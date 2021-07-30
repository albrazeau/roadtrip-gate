from flask import Flask, render_template, request, jsonify, Markup
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import folium
from folium import IFrame
import base64
import glob
import os
import psycopg2
import pandas as pd
from contextlib import closing
from headers import DB_CONNECTION_LOCAL, DB_CONNECTION_DOCKER

# local
# DB_CONNECTION = DB_CONNECTION_LOCAL
# clean_dir = "/home/ubuntu/workbench/roadtrip-gate/data/ready"

# docker
DB_CONNECTION = DB_CONNECTION_DOCKER
clean_dir = "/data/ready"

US_CENTER = ('39.009734', '-97.555620')

app = Flask(__name__)

@app.context_processor
def my_utility_processor():

    def create_map():
        
        fetch_sql = f"""SELECT
                            guid,
                            file_name,
                            date_taken,
                            orientation,
                            ST_X(geom) AS lon_x,
                            ST_Y(geom) AS lat_y
                        FROM
                            roadtrip.images;"""

        with closing(psycopg2.connect(DB_CONNECTION)) as conn:
            df = pd.read_sql(fetch_sql, conn)

        folium_map = folium.Map(location=US_CENTER, 
        zoom_start=4, scrollWheelZoom=False,  
        tiles="Stamen Terrain")

        for idx in range(len(df)):

            img_name = df.iloc[idx]['file_name']
            fullpath = f"{clean_dir}/{img_name}"
            lon = df.iloc[idx]['lon_x']
            lat = df.iloc[idx]['lat_y']

            # resize appropriately
            image = Image.open(fullpath)
            width, height = image.size
            width = width + 25
            height = height + 25

            encoded = base64.b64encode(open(fullpath, 'rb').read())
            html = '<img src="data:image/JPG;base64,{}">'.format
            
            iframe = IFrame(html(encoded.decode("UTF-8")), width=width, height=height)
            
            popup = folium.Popup(iframe, max_width=width+25)
            tooltip = img_name.replace("_"," ")
            
            folium.Marker(location=(lat, lon), tooltip=tooltip, popup=popup, icon=folium.Icon(color='blue')).add_to(folium_map)

        return Markup(folium_map._repr_html_())

        def jeep_image():
            

    return dict(create_map=create_map)

@app.route("/")
def home():

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
