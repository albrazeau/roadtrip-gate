from flask import Flask, render_template, request, jsonify, Markup
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import folium
from folium import IFrame
import folium.plugins as plugins
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
                            attachment_id,
                            filepath,
                            caption,
                            date_taken,
                            ST_X(geom) AS lon_x,
                            ST_Y(geom) AS lat_y
                        FROM
                            roadtrip.images;"""

        with closing(psycopg2.connect(DB_CONNECTION)) as conn:
            df = pd.read_sql(fetch_sql, conn)

        folium_map = folium.Map(location=US_CENTER, 
        zoom_start=4, scrollWheelZoom=False, tiles=None)

        draw_line = list(df.sort_values(by='date_taken')[['lat_y', 'lon_x']].apply(tuple, axis=1))
        folium.PolyLine(draw_line, color="#c20dff", weight=2.5, opacity=1).add_to(folium_map)

        folium_map.add_child(plugins.Geocoder())
        folium.TileLayer('openstreetmap', name = 'Street').add_to(folium_map)
        folium.TileLayer('Stamen Terrain', name = 'Terrain').add_to(folium_map)
        folium.TileLayer(
            tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr = 'Esri',
            name = 'Satellite'
        ).add_to(folium_map)
        folium.LayerControl().add_to(folium_map)
        folium_map.add_child(plugins.Fullscreen(position='topleft', title='Full Screen', title_cancel='Exit Full Screen', force_separate_button=False))

        for idx in range(len(df)):

            img_name = df.iloc[idx]['caption']
            filepath = df.iloc[idx]['filepath']
            lon = df.iloc[idx]['lon_x']
            lat = df.iloc[idx]['lat_y']

            # resize appropriately
            image = Image.open(filepath)
            width, height = image.size
            width = width + 25
            height = height + 25

            encoded = base64.b64encode(open(filepath, 'rb').read())
            html = '<img src="data:image/JPG;base64,{}">'.format
            
            iframe = IFrame(html(encoded.decode("UTF-8")), width=width, height=height)
            
            popup = folium.Popup(iframe, max_width=width+25)
            tooltip = img_name.replace("_"," ")
            
            folium.Marker(location=(lat, lon), tooltip=tooltip, popup=popup, icon=folium.Icon(color='blue')).add_to(folium_map)

        return Markup(folium_map._repr_html_())

    return dict(create_map=create_map)

@app.route("/")
def home():

    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
