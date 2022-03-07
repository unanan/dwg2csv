# import geopandas as gpd
#
# dwg_1_1_path = r"E:\projects\dwg2csv\resources\1-1.dwg"
# dwg_C1_1_path = r"E:\projects\dwg2csv\resources\C1-1.dwg"
#
# shape= gpd.read_file(dwg_1_1_path)
# shape.head()
# shape['Layer'].value_counts()
# arr=shape['Layer'].unique()
# print(arr)
#
# for i in arr:
#     export=shape[(shape.Layer == i)]
#     export.to_file(driver = 'ESRI Shapefile', filename= i+".shp")



if __name__ == '__main__':
    import fiona
    print(fiona.__version__)
