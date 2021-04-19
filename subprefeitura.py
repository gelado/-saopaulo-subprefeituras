# Python script para AWS Lambda
# Le uma pasta com shapefiles no S3 e, dado determinado lat/long, retorna a sub correspondente
from shapely.geometry import Point
import boto3
import geopandas as gpd
import pandas as pd
import tempfile
import glob
import os
import json

s3 = boto3.resource('s3')


def get_shapefile_from_s3():
    print('Recuperando Files do S3...')
    tempdir = tempfile.mkdtemp()
    bucket = s3.Bucket('lambda-dados')
    for file in bucket.objects.all():
        if file.key.startswith('sp360-geocode/') & file.key.endswith(('.dbf', '.cpg', '.shp', '.shx', '.prj')):
            print(file.key)
            bucket.download_file(file.key, tempdir + '/' + os.path.basename(file.key))
    shapefiles_array = glob.glob(tempdir + '/**/*.shp', recursive=True)
    return shapefiles_array


def get_subprefeituras():
    print('Entrando no get_subprefeituras')
    shapes = get_shapefile_from_s3()
    subs = gpd.read_file(shapes[0])

    subs.set_crs(epsg=31983, inplace=True)
    return subs


def get_latlng_shape(lat, lng):
    print('Pegando Lat Long no shape')
    df = pd.DataFrame({'Lat': [lat], 'Lng': [lng]})
    geometry = [Point(xy) for xy in zip(df.Lng, df.Lat)]
    latlng_shape = gpd.GeoDataFrame(df, geometry=geometry)
    latlng_shape.set_crs(epsg=4289, inplace=True)
    latlng_shape.to_crs(epsg=31983, inplace=True)
    return latlng_shape


def get_subprefeitura_by_latlng(lat, lng):
    print(f'Pesquisando pelas coordenadas {lat} (lat) - {lng} (lng)...')
    subprefeituras_shape = get_subprefeituras()
    latlng_shape = get_latlng_shape(lat, lng)
    for _, sub in subprefeituras_shape.iterrows():
        if latlng_shape.iloc[0].geometry.within(sub.geometry):
            return sub
    return False


def lambda_proxy_response(responseCode, responseBody):
    print(f'Resposta http: {responseCode} - {responseBody}')
    response = {
        'statusCode': responseCode,
        'body': json.dumps(responseBody)
    }
    return response


def main(event, context):
    try:
        if event.get("httpMethod") == "GET":
            coords = event.get("queryStringParameters")
        else:
            coords = event
        lat = float(coords.get("lat"))
        lng = float(coords.get("lng"))
        subprefeitura = get_subprefeitura_by_latlng(lat, lng)

        if subprefeitura is False:
            return lambda_proxy_response(404, "Not Found")
        else:
            dict_json = {
                "id_geosampa": subprefeitura.sp_codigo,
                "id_subprefeitura_mapa": int(subprefeitura.sp_id),
                "nome": subprefeitura.sp_nome
            }
            return lambda_proxy_response(200, dict_json)
    except BaseException as exc:
        return lambda_proxy_response(400, "Incorrect format for lat/lng")

