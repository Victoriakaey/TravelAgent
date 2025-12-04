from amadeus import Client, ResponseError
from typing import Dict, List
import os

class AmadeusService:
    def __init__(self, client_id=None, client_secret=None):
        self.client = Client(
            client_id=client_id or os.getenv("AMADEUS_CLIENT_ID"),
            client_secret=client_secret or os.getenv("AMADEUS_CLIENT_SECRET")
        )

    def get_point_of_interest(self, latitude: float, longitude: float) -> Dict:
        try:
            '''
            What are the popular places in Barcelona (based on a geo location and a radius)
            '''
            response = self.reference_data.locations.points_of_interest.get(latitude=41.397158, longitude=2.160873)
            print(response.data)
        except ResponseError as error:
            raise error
        

    def search_flights(self, origin: str, destination: str, departure_date: str, return_date: str = None, adults: int = 1, currency: str = "USD", number_of_search_results: int = 5) -> List[Dict]:
        try:
            params = {
                "originLocationCode": origin,
                "destinationLocationCode": destination,
                "departureDate": departure_date,
                "adults": adults,
                "currencyCode": currency
            }
            if return_date:
                params["returnDate"] = return_date
                
            response = self.client.shopping.flight_offers_search.get(**params)
            return response.data[:number_of_search_results]
        except ResponseError as error:
            return {"error": error.response.body}
    
    def verify_flight_price(self, flight_offer):
        try:
            response = self.client.shopping.flight_offers.pricing.post(flight_offer)
            return response.data
        except ResponseError as error:
            return {"error": error.response.body}
    
    def book_flight(self, selected_flight,travelers) -> Dict:
        """
        Book a flight based on verified offer
        
        Args:
            travelers: List of traveler information dictionaries
            contact: Contact information dictionary
            
        Returns:
            Dict containing booking confirmation details
        """
        try:
            
            response = self.client.booking.flight_orders.post(selected_flight, travelers)
            return response.data
        except ResponseError as error:
            return {"error": error.response.body}
        
    def search_hotels_by_city(self, city_code: str,  radius: int = 5, amenities: List[str] = [], number_of_search_results: int = 5) -> Dict:
        """
        Search for hotels using Amadeus API
        
        Args:
            city_code: City IATA code
            radius: Search radius in KM
            
        Returns:
            Dict containing hotel search results
        """
        
        try:
            response = self.client.reference_data.locations.hotels.by_city.get(
                cityCode=city_code,
                radius=radius,
                radiusUnit='KM',
                amenities=amenities
            )
            return response.data[:number_of_search_results]
        except ResponseError as error:
            return {"error": error.response.body}
    
    def search_hotels_by_coordinates(self, latitude: float, longitude: float, radius: int = 5, amenities: List[str] = [], number_of_search_results: int = 5) -> Dict:
        """
        Get hotels based on geolocation coordinates
        
        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
            radius: Search radius in KM
            amenities: List of amenities to search for
            
        Returns:
            Dict containing hotel search results
        """
        
        try:
            response = self.client.reference_data.locations.hotels.by_geocode.get(
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                radiusUnit='KM',
                amenities=amenities
            )
            return response.data[:number_of_search_results]
        except ResponseError as error:
            return {"error": error.response.body}

    def find_and_confirm_rates_hotel(self, hotel_id: str, check_in_date: str, check_out_date: str, adults: int = 1) -> Dict:
        """
        Find and confirm rates for a hotel using Amadeus API
        
        Args:
            hotel_id: Hotel ID
            check_in_date: Check-in date in YYYY-MM-DD format
            check_out_date: Check-out date in YYYY-MM-DD format
            adults: Number of adults
        Returns:
            Dict containing rate confirmation results
        """
        
        try:
            response = self.client.shopping.hotel_offers_search.get(
                hotelIds=hotel_id,
                checkInDate=check_in_date,
                checkOutDate=check_out_date,
                adults=adults
            )
            return response.data[:5]
        except ResponseError as error:
            return {"error": error.response.body}
        
    def get_tours(self, latitude: float, longitude: float, radius:int = 1) -> Dict:
        """
        Get tours based on geolocation coordinates
        
        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
            
        Returns:
            Dict containing tour information
        """
        
        try:
            response = self.client.shopping.activities.get(latitude=latitude, longitude=longitude, radius=radius)
            return response.data
        except ResponseError as error:
            return {"error": error.response.body}
        
    def get_geocode_from_destination(self, destination: str) -> Dict:
        """
        Get the latitude and longitude of a destination (e.g. city name) using Amadeus location API

        Args:
            destination: Name of the city or airport

        Returns:
            Dict with 'latitude' and 'longitude', or {"error": "..."} if not found
        """
        try:
            response = self.client.reference_data.locations.get(
                keyword=destination,
                subType=Client.location.ANY
            )
            locations = response.data
            if not locations:
                return {"error": f"No geolocation found for destination: {destination}"}
            
            # Return the lat/lng of the top result
            coordinates = locations[0].get('geoCode')
            if coordinates:
                return {
                    "latitude": coordinates["latitude"],
                    "longitude": coordinates["longitude"]
                }
            else:
                return {"error": "No geoCode field found in response"}

        except ResponseError as error:
            return {"error": error.response.body}


# import os
# from dotenv import load_dotenv
# def main():
#     load_dotenv() 
#     amadeus_service = AmadeusService()
#     # Example usage:
#     # poi = amadeus_service.get_point_of_interest(41.397158, 2.160873)
#     # print(poi)
#     hotels = amadeus_service.find_and_confirm_rates_hotel("HLCDG342", "2025-10-10", "2025-10-15", adults=2)
#     print(hotels)

# if __name__ == "__main__":
#     main()