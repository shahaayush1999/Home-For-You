#!/usr/bin/env python
# coding: utf-8

import json
from urllib import request, parse
import time
import math

printing = 1


def convert_coord_to_kms(latitude, longitude):
	y = float(latitude) * 110.574
	x = float(longitude) * 111.32 * math.cos(math.radians(latitude))
	return (x, y)

class Cell:
	def __init__(self, feature_name_list):
		self.params = dict(zip(feature_name_list, [0 for x in range(len(feature_name_list))]))
		self.weight = 1

	def add_feature(self, feature_name, amount):
		if not (0 <= amount <= 1):
			print(f"Failed to bump {feature_name} by {amount}")
			return

		# 1111111 Enable this
		self.params[feature_name] = self.params[feature_name] + amount
		# 2222222 Or Enable this
		# self.params[feature_name] = amount if (amount > self.params[feature_name]) else self.params[feature_name]

	def evaluate(self):
		exponent = 1
		for x in self.params.values():
			if x <= 0:
				exponent = 0
				break
			elif 0 < x <= 1:
				exponent = exponent * x
			else:
				continue
		self.weight = 2 ** exponent

	def get_weight(self):
		return round(self.weight, 3)

	def __str__(self):
		string = ''
		for key, value in self.params.items():
			string = string + str(key[:3]) + ':' + str(value) + ', '
		return 'Wt:' + str(self.weight) + ', ' + string[:-2]


class Map:
	# lat and lon are for origin
	# Radius param is the max dist in kms person is willing to travel from around the origin. Value sent for api calls.
	# grid_res gives the number of cells in the grid eg. grid_res = 11
	# features_list = [gym, spa, mall]
	def __init__(self, latitude, longitude, radius, grid_res, features_list):

		# API key for google places query
		self.API_KEY = "AIzaSyArNt6OwUPx2124XVlbiaxdwXsoQGSl0Ig"

		# Origin Coordinates
		self.origin = [float(latitude), float(longitude)]
		# Origin coords converted to kms
		self.origin_in_kms = list(convert_coord_to_kms(latitude, longitude))
		# Radius = Max distance in kms person is willing to travel, rounded above to 2
		self.radius = radius
		# Grid resolution, always odd
		self.grid_res = grid_res if (grid_res % 2 == 1) else (grid_res + 1)
		# Selected number of features by the user from the app
		self.number_of_features = len(features_list)
		# Requirements list eg. [gym, spa, point of interest]
		self.features_list = features_list
		# Actual data structure for storing a 2d array of class Cell
		self.grid = [[Cell(self.features_list) for i in range(self.grid_res)] for j in range(self.grid_res)]
		# Grid left, right, bottom, top distance from equator/prime meridian in kilometers
		self.left, self.right = self.origin_in_kms[1] - self.radius, self.origin_in_kms[1] + self.radius
		self.bottom, self.top = self.origin_in_kms[0] - self.radius, self.origin_in_kms[0] + self.radius
		# Length of map edge which will be twice of specified radius
		self.map_edge = 2 * self.radius
		# Length of edge of each individual cells (which are squares)
		self.cell_edge = self.map_edge / self.grid_res

	# helper function to bump_feature
	def add_feature_to_cell(self, row_index, col_index, feature_name, amount):
		if not ((-1 < row_index < self.grid_res) and (-1 < col_index < self.grid_res)):
			print(
				f"Error: Cannot bump {feature_name} by {amount} on {row_index}, {col_index}")
			return
		self.grid[row_index][col_index].add_feature(feature_name, amount)
		if printing == 1:
			print(f'Bumped {feature_name} by {amount} on {row_index}, {col_index}')

	# helper function to bump_feature
	def calculate_row_col_index(self, kms_from_equator, kms_from_meridian):
		x, y = kms_from_equator, kms_from_meridian
		if not ((self.left < y < self.right) and (self.bottom < x < self.top)):
			print(f"Error: [{x}, {y}] not a part of map, ", end = '')
			return -1, -1
		vertical_displacement = self.top - x
		horizontal_displacement = y - self.left
		row_index = vertical_displacement // self.cell_edge
		col_index = horizontal_displacement // self.cell_edge
		return int(row_index), int(col_index)

	# Need not worry about out of bound indexes because self.add_feat_to_cell handles that so algo here need not check for bounds
	# Feature name = "spa", "gym", etc and place = [dist_above_equator, dist_from_meridian]
	# This function does the heavy lifting of bumping all cells around the specified cell too
	def bump_feature(self, feature_name, place_location):
		row, col = self.calculate_row_col_index(place_location[0], place_location[1])
		if (row == -1) or (col == -1):
			print(f'failing {feature_name}.')
			return
		area_of_impact = int(self.grid_res // 3)
		depreciation = (1 + self.cell_edge) ** 3
		for x in range(row-area_of_impact, row+area_of_impact+1):
			if not (-1 < x < self.grid_res):
				continue
			for y in range(col-area_of_impact, col+area_of_impact+1):
				if not (-1 < y < self.grid_res):
					continue
				dist = abs(x - row) + abs(y - col)
				amount = 1
				for _ in range(dist):
					amount = amount / depreciation
				self.add_feature_to_cell(x, y, feature_name, amount)

	# Helper to fetch_data
	# Fetches data from GIVEN URL and returns a dictionary with lat long in kilometers
	def fetch_places_api_call(self, url):
		feature_object_list = []
		weburl = request.urlopen(url)
		data = weburl.read()
		data_dict = json.loads(data)
		for result in data_dict['results']:
			lat = result["geometry"]["location"]["lat"]
			lon = result["geometry"]["location"]["lng"]
			(lat_in_km, long_in_km) = convert_coord_to_kms(lat, lon)
			# print("lat : ", lat_in_km, " long : ", long_in_km)
			feature_object_list.append([lat_in_km, long_in_km])
		
		try:
			token = data_dict['next_page_token']
			while True:
				base_url = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json?'
				params = 'key=' + self.API_KEY + '&pagetoken=' + token
				url = base_url + params
				if printing == 1:
					print(url)
				weburl = request.urlopen(url)
				data = weburl.read()
				data_dict = json.loads(data)
				if data_dict['status'] == 'INVALID_REQUEST':
					continue
				if len(data_dict['results']) == 0:
					break
				for result in data_dict['results']:
					lat = result["geometry"]["location"]["lat"]
					lon = result["geometry"]["location"]["lng"]
					(lat_in_km, long_in_km) = convert_coord_to_kms(lat, lon)
					# print("lat : ", lat_in_km, " long : ", long_in_km)
					feature_object_list.append([lat_in_km, long_in_km])
				if data_dict.get('next_page_token') is None:
					break
				token = data_dict['next_page_token']
		except:
			pass
		
		return feature_object_list[0:20]

	# Helper to generate_heatmap
	def fetch_data(self):
		# Places API base url for loading gym, spa, etc
		base_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
		# Template for encoding parameters in the url
		url_parameters = {"location": ",".join(list(map(str, self.origin))),
						  "radius": int(self.radius * 1000),
						  "type": None,
						  "key": self.API_KEY}
		list_of_places_lists = []
		places_list = []
		for feature_name in self.features_list:
			url_parameters['type'] = feature_name
			url = base_url + parse.urlencode(url_parameters, quote_via=parse.quote, safe="/,")
			if printing == 1:
				print(url)
			places_list = self.fetch_places_api_call(url)
			list_of_places_lists.append(places_list)
		zipped_features_and_objects = dict(zip(self.features_list, list_of_places_lists))
		return zipped_features_and_objects

	def generate_heatmap(self, image):
		dict_features_and_objects = self.fetch_data()
		# print(dict_features_and_objects)
		for feature_name, place_list in dict_features_and_objects.items():
			for place in place_list:
				self.bump_feature(feature_name, place)

		map = [[0 for x in range(self.grid_res)] for y in range(self.grid_res)]
		
		for x in range(self.grid_res):
			for y in range(self.grid_res):
				self.grid[x][y].evaluate()
				# print(f'Grid[{x}][{y}]: ', end='')
				# print(self.grid[x][y])
				map[x][y] = self.grid[x][y].get_weight() - 1
			print('')

		for x in map:
			for y in x:
				print(f'{str(y)[0:3]}' + '\t', end='')
			print('')

	def impose_heatmap_on_image(self):
		pass

	def add_image(self):
		pass



if __name__ == '__main__':
	origin = [18.509458, 73.847296]
	features_list = ['shopping_mall', 'park', 'gym']
	radius_in_meters = 2000
	grid_res = 11
	radius_in_kms = radius_in_meters / 1000
	city_map = Map(origin[0], origin[1], radius_in_kms, grid_res, features_list)
	# # To print all map variables
	# for value in vars(city_map):
	# 	if value == 'grid':
	# 		continue
	# 	print(str(value) + ': ' + str(city_map.__dict__[value]))
	city_map.generate_heatmap(None)









dummy = '''
SAMPLE
origin = [18.509458, 73.847296]

# Requirements added from given supported types at https://developers.google.com/places/web-service/supported_types
# Requirements list to be posted from Android app, hard-code THIS list to android app

requirements = [# Food
#                 'bar',
#                 'cafe',
				'restaurant',
#                 'movie_theater',
#                 'night_club',
				
				# Recreational places
#                 'park',
				'tourist_attraction'
				
				# Shopping
#                 'convenience_store',
#                 'department_store',
#                 'grocery_or_supermarket',
#                 'supermarket',
#                 'shopping_mall',
#                 'store',
				
				# Pharma
#                 'pharmacy',
#                 'drugstore',
				
				# Transport
#                 'bus_station',
#                 'train_station',
#                 'transit_station',
#                 'subway_station',
#                 'gas_station',
				
				'gym']

'''
