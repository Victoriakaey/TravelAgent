import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging
import os
from dotenv import load_dotenv
from google.maps import places_v1
from google.type import latlng_pb2

from google.maps import routing_v2
from google.maps.routing_v2 import ComputeRoutesRequest, Waypoint, Location
from google.maps.routing_v2.types import RouteTravelMode

load_dotenv()
class GoogleMapsService:
    def __init__(self):
        self._client_places = None
        self._client_routes = None
    
    async def _get_client_places(self):
        if self._client_places is None:
            self._client_places = places_v1.PlacesAsyncClient(
                client_options={"api_key": os.getenv("GOOGLE_MAPS_API_KEY")}
            )
        return self._client_places
    
    async def _get_client_routes(self):
        if self._client_routes is None:
            self._client_routes = routing_v2.RoutesAsyncClient(
                client_options={"api_key": os.getenv("GOOGLE_MAPS_API_KEY")}
            )
        return self._client_routes

    async def text_search(self, search_query:str) -> places_v1.SearchTextResponse:
        self._client_places = await self._get_client_places()
        # # Coordinates and radius for the location bias
        # lat = 51.516177
        # lng = -0.127245
        # radius_meters = 1000.0
        # # Create the LatLng object for the center
        # center_point = latlng_pb2.LatLng(latitude=lat, longitude=lng)
        # # Create the Circle object
        # circle_area = places_v1.types.Circle(
        #     center=center_point,
        #     radius=radius_meters
        # )
        # # Create the location bias circle
        # location_bias = places_v1.SearchTextRequest.LocationBias(
        #     circle=circle_area
        # )
        # Define the search query and other parameters
        # search_query = "restaurants with outdoor seating"
        # min_place_rating = 4.0
        # Build the request
        request = places_v1.SearchTextRequest(
            text_query=search_query,
            # location_bias=location_bias,
            # min_rating=min_place_rating,
            # open_now=True,
            # price_levels=[
            #     places_v1.types.PriceLevel.PRICE_LEVEL_MODERATE,
            #     places_v1.types.PriceLevel.PRICE_LEVEL_EXPENSIVE
            # ]
        )
        # Set the field mask
        fieldMask = "places.displayName,places.formattedAddress,places.id,places.types,places.rating,places.priceRange,places.currentOpeningHours,places.location"
        # Make the request
        response = await self._client_places.search_text(request=request, metadata=[("x-goog-fieldmask",fieldMask)])
        return response

    async def compute_routes(self,origin_coords, destination_coords, intermediates_coords=None, travel_mode=RouteTravelMode.DRIVE, optimize_order=False):
        self._client_routes = await self._get_client_routes()

        intermediates = []
        if intermediates_coords:
            for coords in intermediates_coords:
                intermediates.append(Waypoint(
                    location=Location(lat_lng=coords)
                ))

        request = ComputeRoutesRequest(
            origin=Waypoint(
                location=Location(lat_lng=origin_coords)
            ),
            destination=Waypoint(
                location=Location(lat_lng=destination_coords)
            ),
            intermediates=intermediates,
            travel_mode=travel_mode,
            optimize_waypoint_order=optimize_order
        )

        response = await self._client_routes.compute_routes(request=request, metadata=[("x-goog-fieldmask", "*")])
        return response
            

# gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))

# print('places:',gmaps.places("Effel Tower"))
# print('places_nearby:',gmaps.places_nearby(location=(48.8588443, 2.2943506), radius=1000, type="restaurant"))
