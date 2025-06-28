"""Unit tests for calculation FSM states."""

import pytest
from aiogram.fsm.state import State

from bot.states.calc_states import CalcStates, CalcData


class TestCalcStates:
    """Test CalcStates FSM group."""

    def test_states_exist(self):
        """Test that all required states exist."""
        assert hasattr(CalcStates, "selecting_pair")
        assert hasattr(CalcStates, "entering_amount")
        assert hasattr(CalcStates, "confirming_calculation")
        assert hasattr(CalcStates, "showing_result")

    def test_states_are_state_instances(self):
        """Test that all states are State instances."""
        assert isinstance(CalcStates.selecting_pair, State)
        assert isinstance(CalcStates.entering_amount, State)
        assert isinstance(CalcStates.confirming_calculation, State)
        assert isinstance(CalcStates.showing_result, State)

    def test_states_have_unique_names(self):
        """Test that all states have unique names."""
        states = [
            CalcStates.selecting_pair,
            CalcStates.entering_amount,
            CalcStates.confirming_calculation,
            CalcStates.showing_result,
        ]

        state_names = [state.state for state in states]
        assert len(state_names) == len(set(state_names))

    def test_states_belong_to_group(self):
        """Test that all states belong to CalcStates group."""
        assert CalcStates.selecting_pair.group == CalcStates
        assert CalcStates.entering_amount.group == CalcStates
        assert CalcStates.confirming_calculation.group == CalcStates
        assert CalcStates.showing_result.group == CalcStates

    def test_state_string_representation(self):
        """Test state string representations."""
        assert "selecting_pair" in str(CalcStates.selecting_pair)
        assert "entering_amount" in str(CalcStates.entering_amount)
        assert "confirming_calculation" in str(CalcStates.confirming_calculation)
        assert "showing_result" in str(CalcStates.showing_result)


class TestCalcData:
    """Test CalcData constants."""

    def test_data_keys_exist(self):
        """Test that all required data keys exist."""
        assert hasattr(CalcData, "BASE_CURRENCY")
        assert hasattr(CalcData, "QUOTE_CURRENCY")
        assert hasattr(CalcData, "AMOUNT")
        assert hasattr(CalcData, "RATE_DATA")
        assert hasattr(CalcData, "CALCULATION_RESULT")
        assert hasattr(CalcData, "MESSAGE_ID")
        assert hasattr(CalcData, "USER_ID")
        assert hasattr(CalcData, "USERNAME")
        assert hasattr(CalcData, "NOTIFICATION_SENT")
        assert hasattr(CalcData, "MANAGER_ID")

    def test_data_keys_are_strings(self):
        """Test that all data keys are strings."""
        assert isinstance(CalcData.BASE_CURRENCY, str)
        assert isinstance(CalcData.QUOTE_CURRENCY, str)
        assert isinstance(CalcData.AMOUNT, str)
        assert isinstance(CalcData.RATE_DATA, str)
        assert isinstance(CalcData.CALCULATION_RESULT, str)
        assert isinstance(CalcData.MESSAGE_ID, str)
        assert isinstance(CalcData.USER_ID, str)
        assert isinstance(CalcData.USERNAME, str)
        assert isinstance(CalcData.NOTIFICATION_SENT, str)
        assert isinstance(CalcData.MANAGER_ID, str)

    def test_data_keys_values(self):
        """Test data key values."""
        assert CalcData.BASE_CURRENCY == "base_currency"
        assert CalcData.QUOTE_CURRENCY == "quote_currency"
        assert CalcData.AMOUNT == "amount"
        assert CalcData.RATE_DATA == "rate_data"
        assert CalcData.CALCULATION_RESULT == "calculation_result"
        assert CalcData.MESSAGE_ID == "message_id"
        assert CalcData.USER_ID == "user_id"
        assert CalcData.USERNAME == "username"
        assert CalcData.NOTIFICATION_SENT == "notification_sent"
        assert CalcData.MANAGER_ID == "manager_id"

    def test_data_keys_unique(self):
        """Test that all data keys are unique."""
        keys = [
            CalcData.BASE_CURRENCY,
            CalcData.QUOTE_CURRENCY,
            CalcData.AMOUNT,
            CalcData.RATE_DATA,
            CalcData.CALCULATION_RESULT,
            CalcData.MESSAGE_ID,
            CalcData.USER_ID,
            CalcData.USERNAME,
            CalcData.NOTIFICATION_SENT,
            CalcData.MANAGER_ID,
        ]

        assert len(keys) == len(set(keys))

    def test_data_keys_naming_convention(self):
        """Test that data keys follow snake_case convention."""
        keys = [
            CalcData.BASE_CURRENCY,
            CalcData.QUOTE_CURRENCY,
            CalcData.AMOUNT,
            CalcData.RATE_DATA,
            CalcData.CALCULATION_RESULT,
            CalcData.MESSAGE_ID,
            CalcData.USER_ID,
            CalcData.USERNAME,
            CalcData.NOTIFICATION_SENT,
            CalcData.MANAGER_ID,
        ]

        for key in keys:
            # Check snake_case: lowercase letters, numbers, and underscores only
            assert key.islower() or "_" in key
            assert key.replace("_", "").replace("-", "").isalnum()
