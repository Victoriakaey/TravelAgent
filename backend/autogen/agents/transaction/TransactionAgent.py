import logging
from autogen_core import CancellationToken
from typing import AsyncGenerator, Sequence
from autogen_agentchat.base import Response
from autogen_agentchat.agents import AssistantAgent
from autogen_core.models import ChatCompletionClient
from typing import Any, AsyncGenerator, Sequence, Dict, List
from autogen_agentchat.messages import BaseAgentEvent,BaseChatMessage, TextMessage

from autogen.services import AmadeusService, LocalStateService, RedisStorage, TimingTracker

logger = logging.getLogger(__name__)

class TransactionAgent(AssistantAgent):
    def __init__(
        self,
        name: str,
        session_id: str,
        user_profile: dict,
        user_travel_details: dict,
        redis_store: RedisStorage,
        model_client: ChatCompletionClient,
        timer_client: TimingTracker,
        time_log_filename: str,
        amadeus_service=None,
        **kwargs: Any,):

        # added session_id here for redis session --> TODO: might need to see if we should use uuid or not, prob doesn't matter that much tho
        self.amadeus_service = amadeus_service or AmadeusService()
        self._name = name
        self._session_id = session_id 
        self._redis_store = redis_store
        self._search_agent_name = "SearchAgent"
        self._type_of_agent = "TransactionService"
        self._local_state_service = LocalStateService(redis_store=self._redis_store)
        self.default_tools=[
            self.show_travelers_information,
            self.process_traveler_selection,
            self.request_new_traveler_info,
            self.book_flight,
            self.book_hotel
        ]
        
        # self._inner_messages: List[BaseAgentEvent | BaseChatMessage] = []
        # fetch_mcp_server = StdioServerParams(command="uvx", args=["mcp-server-fetch"])
        # self.tools = await mcp_server_tools(fetch_mcp_server)
        super().__init__(self._name, model_client, tools= self.default_tools, description="Handles secure payment processing, booking through travel provider APIs, reservation management, and compliance with financial regulations.", 
        system_message="""You are a Transaction Agent specializing in secure booking and payment processing for travel services. After the user have selected their preferred flights, you should call show_travelers_information to retrieve existing traveler profiles related to current user and ask the user whether they want to:
        1. Book flights for the travelers listing above (let the user select the travelers).
        2. Add new travelers to the system (call request_new_traveler_info).
        With the user's selected travelers, you should format it into an index list and call process_traveler_selection to get the selected travelers. After that, you should call book_flight to finalize the booking.

        Provide clear confirmation details and reservation numbers after successful bookings.
        """, **kwargs)

        self.timer = timer_client
        self.time_log_filename = time_log_filename

        self._content_generation_agent_name = "ContentGenerationAgent"
        self.number_of_rounds = 0

        self.user_profile = user_profile
        self.user_travel_details = user_travel_details

        self.perferences = user_profile.get("preferences", [])
        self.constraints = user_profile.get("constraints", [])

    def get_number_of_rounds(self) -> int:
        return self.number_of_rounds

    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        self.number_of_rounds += 1
        timer_tag = f"transaction:{self.number_of_rounds}_streaming_run"
        self.timer.start(timer_tag)
        # Get user's last message
        last_msg = messages[-1].content.lower() if messages else ""

        # Cancel booking detection
        cancel_keywords = ["cancel", "no booking", "cancel booking", "cancel reservation", "stop booking"]
        if any(kw in last_msg for kw in cancel_keywords):
        
            self.timer.stop(timer_tag)
            self.timer.save_as_text(filename=self.time_log_filename)
            yield Response(
                chat_message=TextMessage(
                    content=f"[TransactionAgent] Booking canceled by user. Session `{self._session_id}` marked as no-booking.",
                    source=self.name
                )
            )
            return

        # Normal flow
        async for item in super().on_messages_stream(messages, cancellation_token):
            yield item

        # counts = await self.get_preferences_and_constraints_counts()
        self.timer.stop(timer_tag)
        logger.info(f"[TransactionAgent] Finished processing transaction, and spent {self.timer.execution_times.get(timer_tag, 0)} seconds.")
        self.timer.save_as_text(filename=self.time_log_filename)
        yield Response(
            chat_message=TextMessage(
                content=f"[TransactionAgent] Finished processing transaction and saving data to state for session `{self._session_id}`.",
                source=self.name
            )
        )

    async def is_canceled(self) -> bool:
        """Check if the user has canceled the booking."""
        try:
            flag = await self._local_state_service.aget_flag(self._session_id, "user_confirmed_no_booking")
            return bool(flag)
        except Exception as e:
            logger.error(f"[TransactionAgent] Failed to check user_confirmed_no_booking flag: {e}")
            return False

    async def show_travelers_information(self) -> Dict:
        travelers = await self._local_state_service.get_travelers(self._name, self._session_id)
        return {"status": "success" if travelers else "empty", "travelers": travelers}
    
    async def process_traveler_selection(self, selected_indices: List[int]) -> Dict:
        session_id = self._session_id
        
        # get available travelers from state service
        available_travelers = await self._local_state_service.get_travelers(self._name, self._session_id)
        
        if not available_travelers:
            return {"status": "error", "message": "No travelers available"}
        
        # check indexes
        selected_travelers = []
        for idx in selected_indices:
            if 1 <= idx <= len(available_travelers):
                selected_travelers.append(available_travelers[idx-1])
        
        logger.info(f"[TransactionAgent] Selected travelers: {selected_travelers}")
        
        # store selected travelers in state service
        await self._local_state_service.set_selected_item(self._search_agent_name, self._session_id, "travelers", selected_travelers)
        
        return {
            "status": "success", 
            "message": f"Selected {len(selected_travelers)} travelers",
            "selected_travelers": [
                f"{t['name']['firstName']} {t['name']['lastName']}" 
                for t in selected_travelers
            ]
        }
    
    def request_new_traveler_info(self) -> Dict:
        # Request new traveler information
        return {"action": "show_traveler_form", "session_id": self._session_id}
    
    async def book_flight(self):
        travelers = await self._local_state_service.get_selected_item(self._search_agent_name, self._session_id, "travelers")
        selected_flight = await self._local_state_service.get_selected_item(self._search_agent_name, self._session_id, "flight")
        result = self.amadeus_service.book_flight(selected_flight,travelers)
        if "error" in result:
            return {"status": "error", "message": result["error"]}
        else:
            return {"status": "success", "message": "Flight booked successfully!", "details": result}
    
    def build_booking_link(self,hotel_data):
        self.timer.start("transaction:build_booking_link")
        lat = hotel_data['hotel']['latitude']
        lng = hotel_data['hotel']['longitude']
        checkin = hotel_data['offers'][0]['checkInDate']
        checkout = hotel_data['offers'][0]['checkOutDate']
        self.timer.stop("transaction:build_booking_link")
        logger.info(f"[TransactionAgent] Finished building booking link and spent {self.timer.execution_times.get('transaction:build_booking_link', 0)} seconds.")
        return f"https://www.booking.com/searchresults.html?latitude={lat}&longitude={lng}&checkin={checkin}&checkout={checkout}"
    
    async def book_hotel(self):
        self.timer.start("transaction:book_hotel")
        selected_hotel = await self._local_state_service.get_selected_item(self._search_agent_name, self._session_id, "hotel")
        logger.info(f"[TransactionAgent] Selected hotel: {selected_hotel}")
        booking_link = self.build_booking_link(selected_hotel)

        self.timer.stop("transaction:book_hotel")
        logger.info(f"[TransactionAgent] Finished booking hotel and spent {self.timer.execution_times.get('transaction:book_hotel', 0)} seconds.")
        return booking_link

'''
curl -X POST http://localhost:8000/autogen/run_agent \
  -H "Content-Type: application/json" \
  -d '{
        "message": "Book me a flight to Paris at May 2",
        "session_id": "testDummyUser_session_001"
      }'
'''