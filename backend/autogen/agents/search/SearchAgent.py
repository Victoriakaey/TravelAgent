import json
import logging
from typing import List, Any
from autogen_core import CancellationToken
from autogen_core import CancellationToken
from autogen_agentchat.base import Response
from typing import AsyncGenerator, Sequence
from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ChatCompletionClient
from google.protobuf.json_format import MessageToDict
from autogen_agentchat.messages import BaseAgentEvent,BaseChatMessage, TextMessage

from ._utils import system_message, search_description
from autogen.services import RedisStorage, AmadeusService, GoogleMapsService, LocalStateService, TimingTracker

from typing import (
    Any,
    AsyncGenerator,
    Sequence,
)

logger = logging.getLogger(__name__)

class SearchAgent(AssistantAgent):
    def __init__(
        self,
        model_client: ChatCompletionClient,
        timer_client: TimingTracker,
        time_log_filename: str,
        session_id: str,
        redis_store: RedisStorage,
        amadeus_service=None, 
        google_maps_service=None,
        fallback: bool = False,
        currency: str = "USD",
        name: str = "SearchAgent",
        number_of_search_results: int = 5,
        **kwargs: Any,):

        self.amadeus_service = amadeus_service or AmadeusService()
        self.google_maps_service = google_maps_service or GoogleMapsService()
        self._search_results = {}
        self.currency = currency
        self.number_of_search_results = number_of_search_results

        self.default_tools = [
            self.search_flights,
            self.search_hotels_by_city,
            self.search_hotels_by_geocode,
            self.verify_flight_price,
            self.find_and_confirm_rates_hotel,
            self.search_tours,
            self.search_places,
            self.compute_routes,
        ]

        self._name = name
        self._session_id = session_id
        self._redis_store = redis_store 
        self._type_of_agent = "SearchService"
        self._user_info_agent = "UserInfoService"
        self._local_state_service = LocalStateService(redis_store=self._redis_store)
        self.timer = timer_client
        self.time_log_filename = time_log_filename

        super().__init__(
            name, 
            model_client, 
            tools= self.default_tools, 
            description=search_description, 
            system_message=system_message
        )

        # self._inner_messages: List[BaseAgentEvent | BaseChatMessage] = []
        # fetch_mcp_server = StdioServerParams(command="uvx", args=["mcp-server-fetch"])
        # self.tools = await mcp_server_tools(fetch_mcp_server)

        self.number_of_rounds = 0
        self.list_of_search_modes = ["flight", "hotel", "place", "tour"]
        self.list_of_search_activities = {
            "searched_mode": [], # flight, hotel_by_city, hotel_by_geocode, place, tour
            "errors": [],
            "flight_searches": [],
            "hotel_searches": [],
            "places_searches": [],
            "tour_searches": [],
            "messages": [],
        }

        self._fallback = fallback

    def get_list_of_search_modes_and_errors(self):
        return {
            "searched_mode": self.list_of_search_activities["searched_mode"], 
            "errors": self.list_of_search_activities["errors"]
        }

    def get_list_of_search_activities(self):
        return self.list_of_search_activities
    
    def get_number_of_rounds(self):
        return self.number_of_rounds

    async def get_user_profile(self):
        timer_tag = f"search:{self.number_of_rounds}_fetch_user_profile"
        self.timer.start(timer_tag)
        logger.info(f"[SearchAgent] Fetching user profile for session {self._session_id}")
        try:
            user_profile = await self._local_state_service.get_user_profile(self._user_info_agent, self._session_id)
            if user_profile:
                logger.info(f"[SearchAgent] User profile fetched successfully")
                logger.verbose(f"[SearchAgent] User profile details: {json.dumps(user_profile, indent=2)}")
                self.timer.stop(timer_tag)
                logger.info(f"[SearchAgent] Fetched user profile, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return user_profile
            else:
                # logger.info(f"[SearchAgent] No user profile found.")
                self.timer.stop(timer_tag)
                logger.info(f"[SearchAgent] No user profile found, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return {}
        except Exception as e:
            logger.error(f"[SearchAgent] Failed to fetch user profile: {e}")
            self.timer.stop(timer_tag)
            logger.info(f"[SearchAgent] Failed to fetch user profile, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return None

    async def get_user_travel_details(self):
        timer_tag = f"search:{self.number_of_rounds}_fetch_user_travel_details"
        self.timer.start(timer_tag)
        try:
            user_travel_detail = await self._local_state_service.get_user_travel_details(self._user_info_agent, self._session_id)
            if user_travel_detail:
                # logger.info(f"[SearchAgent] User travel details fetched successfully")
                logger.verbose(f"[SearchAgent] User travel details: {json.dumps(user_travel_detail, indent=2)}")
                self.timer.stop(timer_tag)
                logger.info(f"[SearchAgent] Fetched user travel details, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return user_travel_detail
            else:
                # logger.info(f"[SearchAgent] No user travel details found.")
                self.timer.stop(timer_tag)
                logger.info(f"[SearchAgent] No user travel details found, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return {}
        except Exception as e:
            logger.error(f"[SearchAgent] Failed to fetch user travel details: {e}")
            self.timer.stop(timer_tag)
            logger.info(f"[SearchAgent] Failed to fetch user travel details, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return None

    async def search_flights(self, origin: str, destination: str, departure_date: str, return_date: str = None, adults: int = 1):
        timer_tag = f"search:{self.number_of_rounds}_flight_search"
        self.timer.start(timer_tag)
        logger.info(f"[SearchAgent] Initiating flight search with parameters: origin={origin}, destination={destination}, departure_date={departure_date}, return_date={return_date}, adults={adults}")
        results = self.amadeus_service.search_flights(origin, destination, departure_date, return_date, adults, self.currency, self.number_of_search_results)
        logger.verbose(f"[SearchAgent] Flight search results: {results}")

        if 'error' in results:
            self.list_of_search_activities["errors"].append({
                "round": self.number_of_rounds,
                "mode": "flight",
                "parameters": {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "adults": adults,
                    "currency": self.currency,
                    "number_of_search_results": self.number_of_search_results
                },
                "details": results['error']
            })
            logger.error(f"[SearchAgent] Flight search error: {results['error']}")

        ### Can fix it in PlanningAgent, just add a note and have it check the date if it's valid; if not, have the UserProxyAgent ask for user for clarification
        await self._local_state_service.store_search_results(self._name, self._session_id, "flight", results)

        flight_search_activity = {
            "round": self.number_of_rounds,
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "adults": adults,
            "results": results
        }

        self.list_of_search_activities["searched_mode"].append((self.number_of_rounds, "flight"))
        self.list_of_search_activities["flight_searches"].append(flight_search_activity)

        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Completed flight search, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return results

    async def verify_flight_price(self, flight_offer_id: int):
        timer_tag = f"search:{self.number_of_rounds}_verify_flight_price"
        self.timer.start(timer_tag)
        logger.info(f"[SearchAgent] Verifying flight offer ID: {flight_offer_id}")
        flight_results = await self._local_state_service.get_search_results(self._name, self._session_id, "flight")
        if not flight_results or flight_offer_id < 1 or flight_offer_id > len(flight_results):
            self.timer.stop(timer_tag)
            logger.error(f"[SearchAgent] Invalid flight offer index: {flight_offer_id}")
            logger.info(f"[SearchAgent] Aborted flight price verification, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return {"error": "Invalid flight offer index"}

        flight = flight_results[flight_offer_id - 1]
        result = self.amadeus_service.verify_flight_price(flight)
        
        if "error" not in result:
            logger.verbose(f"[SearchAgent] Flight verification successful:\nResult:\n{result}\nFlight:\n{flight}")
            await self._local_state_service.set_selected_item(self._name, self._session_id, "flight", flight)
        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Completed flight price verification, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return result

    async def search_hotels_by_city(self, city_code: str,  radius: int = 5, amenities: List[str] = []):
        timer_tag = f"search:{self.number_of_rounds}_hotel_by_city_search"
        self.timer.start(timer_tag)
        logger.info(f"[SearchAgent] Searching hotels in city {city_code} within {radius} km with amenities {amenities}")
        results = self.amadeus_service.search_hotels_by_city(city_code, radius, amenities)
        logger.verbose(f"[SearchAgent] Hotel search results for city {city_code} within {radius} km with amenities {amenities}:\n{results}")

        if 'error' in results:
            self.list_of_search_activities["errors"].append({
                "round": self.number_of_rounds,
                "mode": "hotel_by_city",
                "parameters": {
                    "city_code": city_code,
                    "radius": radius,
                    "amenities": amenities
                },
                "details": results['error']
            })
            logger.error(f"[SearchAgent] Hotel search error: {results['error']}")

        await self._local_state_service.store_search_results(self._name, self._session_id, "hotel", results)

        hotel_search_activity = {
            "round": self.number_of_rounds,
            "city_code": city_code,
            "radius": radius,
            "amenities": amenities,
            "results": results
        }

        self.list_of_search_activities["searched_mode"].append((self.number_of_rounds, "hotel_by_city"))
        self.list_of_search_activities["hotel_searches"].append(hotel_search_activity)

        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Completed hotel search, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return results
    
    async def search_hotels_by_geocode(self, latitude: float, longitude: float, radius: int = 5, amenities: List[str] = []):
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
        timer_tag = f"search:{self.number_of_rounds}_hotel_by_geocode_search"
        self.timer.start(timer_tag)
        logger.info(f"[SearchAgent] Searching hotels near coordinates ({latitude}, {longitude}) within {radius} km with amenities {amenities}")
        results = self.amadeus_service.search_hotels_by_coordinates(latitude, longitude, radius, amenities)
        logger.verbose(f"[SearchAgent] Hotel search results for coordinates ({latitude}, {longitude}) within {radius} km with amenities {amenities}:\n{results}")

        if 'error' in results:
            self.list_of_search_activities["errors"].append({
                "round": self.number_of_rounds,
                "mode": "hotel_by_geocode",
                "parameters": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": radius,
                    "amenities": amenities
                },
                "details": results['error']
            })
            logger.error(f"[SearchAgent] Hotel search error: {results['error']}")

        await self._local_state_service.store_search_results(self._name, self._session_id, "hotel", results)

        hotel_search_activity = {
            "round": self.number_of_rounds,
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius,
            "amenities": amenities,
            "results": results
        }

        self.list_of_search_activities["searched_mode"].append((self.number_of_rounds, "hotel_by_geocode"))
        self.list_of_search_activities["hotel_searches"].append(hotel_search_activity)

        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Completed hotel search, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return results

    async def find_and_confirm_rates_hotel(self, hotel_id:str, check_in_date: str, check_out_date: str, adults: int = 1):
        timer_tag = f"search:{self.number_of_rounds}_hotel_rate_confirmation"
        self.timer.start(timer_tag)
        results = self.amadeus_service.find_and_confirm_rates_hotel(hotel_id, check_in_date, check_out_date, adults)
        # print(f"Hotel search results: {results[0]}")
        if "error" not in results:
            logger.verbose(f"[SearchAgent] Hotel rate confirmation successful:\nResult:\n{results[0]}\nHotel ID:\n{hotel_id}")
            await self._local_state_service.set_selected_item(self._name, self._session_id, "hotel", results[0])
        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Completed hotel rate confirmation, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return results

    async def search_tours(self, latitude:float, longitude: float, radius:int = 1):
        """
        Get tours based on geolocation coordinates
        Args:
            latitude: Latitude of the location
            longitude: Longitude of the location
            radius: Search radius in KM
        Returns:
            Dict containing tour search results
        """
        timer_tag = f"search:{self.number_of_rounds}_tour_search"
        self.timer.start(timer_tag)  

        results = self.amadeus_service.get_tours(latitude, longitude, radius)
        logger.verbose(f"[SearchAgent] Tour search results for coordinates ({latitude}, {longitude}) within {radius} km:\n{results}")

        if 'error' in results:
            self.list_of_search_activities["errors"].append({
                "round": self.number_of_rounds,
                "mode": "tour",
                "parameters": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": radius
                },
                "details": results['error']
            })
            logger.error(f"[SearchAgent] Tour search error: {results['error']}")


        await self._local_state_service.store_search_results(self._name, self._session_id, "tour", results)

        tour_search_activity = {
            "round": self.number_of_rounds,
            "latitude": latitude,
            "longitude": longitude,
            "radius": radius,
            "results": results
        }

        self.list_of_search_activities["searched_mode"].append((self.number_of_rounds, "tour"))
        self.list_of_search_activities["tour_searches"].append(tour_search_activity)

        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Completed tour search, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return results
    
    async def search_places(self,text_query:str):
        timer_tag = f"search:{self.number_of_rounds}_places_search"
        self.timer.start(timer_tag)
        response = await self.google_maps_service.text_search(text_query)
        places_data = response.places

        if not places_data: return None

        result = places_data[0]
        result_dict = MessageToDict(response.places[0]._pb)

        if 'error' in result_dict:
            self.list_of_search_activities["errors"].append({
                "round": self.number_of_rounds,
                "mode": "place",
                "parameters": {
                    "text_query": text_query
                },
                "details": result_dict['error']
            })
            logger.error(f"[SearchAgent] Places search error: {result_dict['error']}")

        logger.verbose(f"[SearchAgent] Search places result: {result_dict}")
        
        places_search_activity = {
            "round": self.number_of_rounds,
            "text_query": text_query,
            "results": result_dict
        }
            
        self.list_of_search_activities["searched_mode"].append((self.number_of_rounds, "place"))
        self.list_of_search_activities["places_searches"].append(places_search_activity)

        await self._local_state_service.add_place(self._name, self._session_id, result_dict)
        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Completed places search, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return result
        
    async def compute_routes(self):
        """
        Compute routes between origin and destination using Google Maps.
        Args:
            origin_coords: Tuple (lat, lng) for origin
            destination_coords: Tuple (lat, lng) for destination
            intermediates_coords: List of (lat, lng) tuples for waypoints (optional)
            travel_mode: Travel mode, e.g., RouteTravelMode.DRIVE (optional)
            optimize_order: Whether to optimize waypoint order (bool)
        Returns:
            The response from Google Maps routing API
        """
        timer_tag = f"search:{self.number_of_rounds}_compute_routes"
        self.timer.start(timer_tag)
        # Default travel mode to DRIVE if not specified
        logger.verbose(f"[SearchAgent] Computing routes for session {self._session_id}")
        itineraries = await self._local_state_service.get_generated_plan(self._name, self._session_id)
        origin_coords = itineraries[0]['places'][0]['location']
        destination_coords = itineraries[0]['places'][-1]['location']
        intermediates_coords = [place['location'] for place in itineraries[0]['places'][1:-1]]
        
        response = await self.google_maps_service.compute_routes(
            origin_coords, destination_coords, intermediates_coords
        )
        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Completed route computation, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return response
    
    def get_re_search_text(self):
        timer_tag = f"search:{self.number_of_rounds}_get_re_search_text"
        self.timer.start(timer_tag)
        searched_mode = self.get_searched_modes()
        logger.debug(f"[ReSearch] Searched modes: {searched_mode}")

        # Map logical mode → corresponding searches
        search_map = {
            "flight": self.list_of_search_activities.get("flight_searches", []),
            "hotel": self.list_of_search_activities.get("hotel_searches", []),
            "place": self.list_of_search_activities.get("places_searches", []),
            "tour": self.list_of_search_activities.get("tour_searches", []),
        }

        # Count summary
        summary_parts = [f"{len(v)} {k}" for k, v in search_map.items()]
        summary_text = "; ".join(summary_parts)
        logger.debug(f"[ReSearch] Search summary: {summary_text}")

        # Unsearched modes
        un_searched = set(self.list_of_search_modes) - set(searched_mode)
        logger.debug(f"[ReSearch] Unsearched modes: {un_searched}")

        # Error modes: searched but empty
        errors = {
            "flight" if m == "flight" else
            "hotel" if m in ["hotel_by_city", "hotel_by_geocode"] else
            m
            for m in searched_mode
            if not search_map.get("hotel" if m in ["hotel_by_city", "hotel_by_geocode"] else m, [])
        }
        logger.debug(f"[ReSearch] Error modes (searched but empty): {errors}")

        # Combine
        re_search_modes = sorted(un_searched | errors)
        logger.debug(f"[ReSearch] Final re_search_modes: {re_search_modes}")

        # Final text for PlanningAgent
        text = (
            f"You have already attempted searches for: {', '.join(searched_mode) or 'none'}. "
            f"Current results summary → {summary_text}. "
        )
        if re_search_modes:
            text += f"Next, reperform the following searches: {', '.join(re_search_modes)}."

        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Generated re-search text, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return text

    def requested_search_mode(self, message_content: str):
        timer_tag = f"search:{self.number_of_rounds}_requested_search_mode"
        self.timer.start(timer_tag)
        message_content_lower = message_content.lower()
        for mode in self.list_of_search_modes:
            if mode in message_content_lower:
                self.timer.stop(timer_tag)
                logger.info(f"[SearchAgent] Determined requested search mode to be {mode}, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
                return mode
        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Returned None value in requested_search_mode, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return None
    
    def get_searched_modes(self):
        timer_tag = f"search:{self.number_of_rounds}_get_searched_modes"
        self.timer.start(timer_tag)
        modes = []
        searched_modes_tuples = self.list_of_search_activities["searched_mode"]
        for mode in searched_modes_tuples:
            if mode[1] == "hotel_by_city" or mode[1] == "hotel_by_geocode":
                modes.append("hotel")
            else:
                modes.append(mode[1])
        
        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Retrieved searched modes (performed search modes) {modes}, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return modes
    
    def has_valid_results(self, mode: str) -> bool:
        timer_tag = f"search:{self.number_of_rounds}_has_valid_results"
        self.timer.start(timer_tag)
        if mode == "hotel":
            results = self.list_of_search_activities.get("hotel_searches", [])
        elif mode == "flight":
            results = self.list_of_search_activities.get("flight_searches", [])
        elif mode == "place":
            results = self.list_of_search_activities.get("places_searches", [])
        elif mode == "tour":
            results = self.list_of_search_activities.get("tour_searches", [])
        else:
            results = []
        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Checked for valid results in mode {mode}, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        return bool(results)  # True if non-empty

    def is_requested_and_performed_search_align(self, message_content: str):
        timer_tag = f"search:{self.number_of_rounds}_is_requested_and_performed_search_align"
        self.timer.start(timer_tag)
        requested_mode = self.requested_search_mode(message_content)
        if not requested_mode:  
            self.timer.stop(timer_tag)
            logger.info(f"[SearchAgent] No specific search mode requested, returning True by default, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return True  # No specific mode requested, so no conflict
        if requested_mode not in self.get_searched_modes():  
            self.timer.stop(timer_tag)
            logger.info(f"[SearchAgent] Requested mode '{requested_mode}' not in searched modes, returning False, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return False  # never performed → Fail
        if not self.has_valid_results(requested_mode): 
            self.timer.stop(timer_tag)
            logger.info(f"[SearchAgent] Requested mode '{requested_mode}' but no valid results for it found, returning False, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
            return False  # performed but got no results → Fail

        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Requested mode '{requested_mode}' has been performed with valid results, returning True, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.") 
        return True  # performed + has results → OK

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        logger.info(f"[SearchAgent] fallback: {self._fallback}")

        self.number_of_rounds += 1
        timer_tag = f"search:{self.number_of_rounds}_streaming_run"
        self.timer.start(timer_tag)
        logger.info(f"[SearchAgent] Starting streaming search for messages for the {self.number_of_rounds}-th times...")
        async for item in super().on_messages_stream(messages, cancellation_token):
            yield item
        agent_state = await self.save_state()
        agent_state['name'] = self.name
        agent_state['session_id'] = self._session_id

        last_message_content = messages[-1].content if messages else ""
        messages_activity = {
            "round": self.number_of_rounds,
            "messages": last_message_content,
        }
        self.list_of_search_activities["messages"].append(messages_activity)

        requested_mode = self.requested_search_mode(last_message_content)
        requested_performed = self.is_requested_and_performed_search_align(last_message_content)

        if self._fallback and not requested_performed:
            error = self.list_of_search_activities["errors"]
            last_error = error[-1] if error else {}
            logger.warning(
                f"[SearchAgent] Conflict detected: PlanningAgent requested '{requested_mode}' "
                f"but SearchAgent has not performed it (or results were empty)."
            )
            yield Response(
                chat_message=TextMessage(
                    content=(
                        f"Task Failed: PlanningAgent requested a '{requested_mode}' search, "
                        f"but either the current {requested_mode} results were empty or an error occurred. "
                        f"Length of {requested_mode} search results: {len(self.list_of_search_activities.get(requested_mode, []))}. "
                        f"Error encountered: {last_error}. "
                        f"Please adjust as needed and re-do the search."
                    ),
                    source=self.name,
                )
            )
            self.timer.stop(timer_tag)
            logger.info(
                f"[SearchAgent] Aborted streaming search for round {self.number_of_rounds}, "
                f"spent {self.timer.execution_times.get(timer_tag, 0)} seconds."
            )
            self.timer.save_as_text(filename=self.time_log_filename)
            return

        yield Response(
            chat_message=TextMessage(
                content=f"[SearchAgent] Finished searching and saving data to state for session `{self._session_id}`.",
                source=self.name
            )
        )

        logger.verbose(f"[SearchAgent] List of search activities so far: {self.list_of_search_activities}\n")
        self.timer.stop(timer_tag)
        logger.info(f"[SearchAgent] Finished streaming search for messages, spent {self.timer.execution_times.get(timer_tag, 0)} seconds to ran.")
        self.timer.save_as_text(filename=self.time_log_filename)

'''
curl -X POST http://localhost:8000/autogen/run_agent \
  -H "Content-Type: application/json" \
  -d '{
        "message": "Book me a flight to Paris at May 2",
        "session_id": "testDummyUser_session_001"
      }'
'''