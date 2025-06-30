"""FSM states for calculation flow.

This module defines the finite state machine states used for the /calc command
to handle multi-step user input for currency exchange calculations.
"""

from aiogram.fsm.state import State, StatesGroup


class CalcStates(StatesGroup):
    """States for calculation flow."""

    # State for selecting currency pair
    selecting_pair = State()

    # State for showing rate and calculate button
    showing_rate = State()

    # State for entering amount to convert
    entering_amount = State()

    # State for confirming calculation
    confirming_calculation = State()

    # State for showing result and waiting for notification
    showing_result = State()


class CalcData:
    """Data keys for calculation flow context."""

    # Selected currency pair
    BASE_CURRENCY = "base_currency"
    QUOTE_CURRENCY = "quote_currency"

    # User input amount
    AMOUNT = "amount"

    # Rate data from API
    RATE_DATA = "rate_data"

    # Calculation result
    CALCULATION_RESULT = "calculation_result"

    # Message ID for editing
    MESSAGE_ID = "message_id"

    # User information
    USER_ID = "user_id"
    USERNAME = "username"

    # Notification status
    NOTIFICATION_SENT = "notification_sent"
    MANAGER_ID = "manager_id"
