"""Tests for notification templates functionality.

This module contains tests for the NotificationTemplates utility class
and template validation functionality.
"""


from services.notification_service import NotificationTemplate
from templates.notification_templates import NotificationTemplates


class TestNotificationTemplatesClass:
    """Test NotificationTemplates utility class."""

    def test_get_default_templates_structure(self):
        """Test that default templates have correct structure."""
        templates = NotificationTemplates.get_default_templates()

        assert isinstance(templates, dict)
        assert len(templates) > 0

        # Check required templates exist
        required_templates = [
            "transaction",
            "rate_request",
            "calculation_request",
            "error",
            "system_alert",
            "high_volume_alert",
            "daily_summary",
            "manager_assignment",
            "markup_change",
            "api_error",
        ]

        for template_name in required_templates:
            assert (
                template_name in templates
            ), f"Required template '{template_name}' not found"
            assert isinstance(templates[template_name], NotificationTemplate)

    def test_transaction_template(self):
        """Test transaction notification template."""
        template = NotificationTemplates.get_template_by_name("transaction")

        assert template is not None
        assert template.title == "💱 Новая транзакция"
        assert template.include_user_info is True
        assert template.include_calculation_details is True
        assert template.include_action_buttons is True

        # Check template contains required variables
        body = template.body_template
        required_vars = [
            "{transaction_id}",
            "{timestamp}",
            "{user_display_name}",
            "{user_id}",
            "{currency_pair}",
            "{direction}",
            "{input_amount}",
            "{output_amount}",
            "{exchange_rate}",
            "{markup_rate}",
            "{markup_amount}",
            "{quote_currency}",
        ]

        for var in required_vars:
            assert (
                var in body
            ), f"Required variable {var} not found in transaction template"

    def test_rate_request_template(self):
        """Test rate request notification template."""
        template = NotificationTemplates.get_template_by_name("rate_request")

        assert template is not None
        assert template.title == "📊 Запрос курса"
        assert template.include_user_info is True
        assert template.include_calculation_details is False
        assert template.include_action_buttons is False

        # Check template contains required variables
        body = template.body_template
        required_vars = [
            "{user_display_name}",
            "{user_id}",
            "{currency_pair}",
            "{timestamp}",
            "{exchange_rate}",
            "{markup_rate}",
        ]

        for var in required_vars:
            assert (
                var in body
            ), f"Required variable {var} not found in rate_request template"

    def test_error_template(self):
        """Test error notification template."""
        template = NotificationTemplates.get_template_by_name("error")

        assert template is not None
        assert template.title == "⚠️ Ошибка системы"
        assert template.include_user_info is True
        assert template.include_calculation_details is False
        assert template.include_action_buttons is False

        # Check template contains required variables
        body = template.body_template
        required_vars = [
            "{transaction_id}",
            "{timestamp}",
            "{error_message}",
            "{user_display_name}",
            "{user_id}",
        ]

        for var in required_vars:
            assert var in body, f"Required variable {var} not found in error template"

    def test_high_volume_alert_template(self):
        """Test high volume alert template."""
        template = NotificationTemplates.get_template_by_name("high_volume_alert")

        assert template is not None
        assert template.title == "📈 Уведомление о крупной сумме"
        assert template.include_user_info is True
        assert template.include_calculation_details is True
        assert template.include_action_buttons is True

    def test_system_alert_template(self):
        """Test system alert template."""
        template = NotificationTemplates.get_template_by_name("system_alert")

        assert template is not None
        assert template.title == "🚨 Системное уведомление"
        assert template.include_user_info is False
        assert template.include_calculation_details is False
        assert template.include_action_buttons is False

    def test_daily_summary_template(self):
        """Test daily summary template."""
        template = NotificationTemplates.get_template_by_name("daily_summary")

        assert template is not None
        assert template.title == "📊 Ежедневная сводка"
        assert template.include_user_info is False
        assert template.include_calculation_details is False
        assert template.include_action_buttons is False

    def test_manager_assignment_template(self):
        """Test manager assignment template."""
        template = NotificationTemplates.get_template_by_name("manager_assignment")

        assert template is not None
        assert template.title == "👨‍💼 Назначение менеджера"
        assert template.include_user_info is False
        assert template.include_calculation_details is False
        assert template.include_action_buttons is False

    def test_markup_change_template(self):
        """Test markup change template."""
        template = NotificationTemplates.get_template_by_name("markup_change")

        assert template is not None
        assert template.title == "📊 Изменение наценки"
        assert template.include_user_info is False
        assert template.include_calculation_details is False
        assert template.include_action_buttons is False

    def test_api_error_template(self):
        """Test API error template."""
        template = NotificationTemplates.get_template_by_name("api_error")

        assert template is not None
        assert template.title == "🔌 Ошибка API"
        assert template.include_user_info is False
        assert template.include_calculation_details is False
        assert template.include_action_buttons is False

    def test_get_template_by_name_existing(self):
        """Test getting existing template by name."""
        template = NotificationTemplates.get_template_by_name("transaction")

        assert template is not None
        assert isinstance(template, NotificationTemplate)
        assert template.title == "💱 Новая транзакция"

    def test_get_template_by_name_non_existing(self):
        """Test getting non-existing template by name."""
        template = NotificationTemplates.get_template_by_name("non_existing_template")
        assert template is None

    def test_get_available_template_names(self):
        """Test getting list of available template names."""
        names = NotificationTemplates.get_available_template_names()

        assert isinstance(names, list)
        assert len(names) > 0

        # Check that all expected templates are in the list
        expected_names = [
            "transaction",
            "rate_request",
            "calculation_request",
            "error",
            "system_alert",
            "high_volume_alert",
            "daily_summary",
            "manager_assignment",
            "markup_change",
            "api_error",
        ]

        for name in expected_names:
            assert (
                name in names
            ), f"Expected template name '{name}' not found in available names"

    def test_create_custom_template_with_defaults(self):
        """Test creating custom template with default parameters."""
        template = NotificationTemplates.create_custom_template(
            title="Custom Template",
            body_template="Custom body with {transaction_id}",
        )

        assert template.title == "Custom Template"
        assert template.body_template == "Custom body with {transaction_id}"
        assert template.include_user_info is True  # Default
        assert template.include_calculation_details is True  # Default
        assert template.include_action_buttons is False  # Default

    def test_create_custom_template_with_custom_params(self):
        """Test creating custom template with custom parameters."""
        template = NotificationTemplates.create_custom_template(
            title="Custom Template",
            body_template="Custom body with {transaction_id}",
            include_user_info=False,
            include_calculation_details=False,
            include_action_buttons=True,
        )

        assert template.title == "Custom Template"
        assert template.body_template == "Custom body with {transaction_id}"
        assert template.include_user_info is False
        assert template.include_calculation_details is False
        assert template.include_action_buttons is True

    def test_get_template_variables_structure(self):
        """Test template variables structure."""
        variables = NotificationTemplates.get_template_variables()

        assert isinstance(variables, dict)
        assert len(variables) > 0

        # Check categories of variables exist
        transaction_vars = [
            "transaction_id",
            "timestamp",
            "currency_pair",
            "direction",
        ]

        user_vars = [
            "user_id",
            "user_display_name",
            "username",
            "full_name",
        ]

        calculation_vars = [
            "input_amount",
            "output_amount",
            "exchange_rate",
            "markup_rate",
            "markup_amount",
            "base_currency",
            "quote_currency",
        ]

        error_vars = [
            "error_message",
            "error_code",
        ]

        all_expected_vars = transaction_vars + user_vars + calculation_vars + error_vars

        for var in all_expected_vars:
            assert (
                var in variables
            ), f"Expected variable '{var}' not found in template variables"
            assert isinstance(
                variables[var], str
            ), f"Variable '{var}' description should be string"
            assert (
                len(variables[var]) > 0
            ), f"Variable '{var}' should have non-empty description"

    def test_template_variables_descriptions(self):
        """Test that template variables have meaningful descriptions."""
        variables = NotificationTemplates.get_template_variables()

        # Test some specific variable descriptions
        assert "identifier" in variables["transaction_id"].lower()
        assert "user" in variables["user_id"].lower()
        assert "currency" in variables["currency_pair"].lower()
        assert "amount" in variables["input_amount"].lower()
        assert "rate" in variables["exchange_rate"].lower()
        assert "error" in variables["error_message"].lower()


class TestTemplateValidation:
    """Test template validation functionality."""

    def test_validate_template_success_minimal(self):
        """Test validation of minimal valid template."""
        template = NotificationTemplate(
            title="Test Template",
            body_template="Simple message",
            include_user_info=False,
            include_calculation_details=False,
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) == 0

    def test_validate_template_success_with_variables(self):
        """Test validation of template with proper variables."""
        template = NotificationTemplate(
            title="Test Template",
            body_template="Hello {user_display_name}! ID: {user_id}, Transaction: {transaction_id}",
            include_user_info=True,
            include_calculation_details=False,
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) == 0

    def test_validate_template_empty_title(self):
        """Test validation with empty title."""
        template = NotificationTemplate(
            title="",
            body_template="Test body",
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) > 0
        assert any("title is required" in error.lower() for error in errors)

    def test_validate_template_empty_body(self):
        """Test validation with empty body."""
        template = NotificationTemplate(
            title="Test Title",
            body_template="",
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) > 0
        assert any("body is required" in error.lower() for error in errors)

    def test_validate_template_unmatched_braces(self):
        """Test validation with unmatched braces."""
        # More opening braces
        template = NotificationTemplate(
            title="Test Title",
            body_template="Hello {user_name} and {another_var",
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) > 0
        assert any("unmatched braces" in error.lower() for error in errors)

        # More closing braces
        template = NotificationTemplate(
            title="Test Title",
            body_template="Hello user_name} and {another_var}",
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) > 0
        assert any("unmatched braces" in error.lower() for error in errors)

    def test_validate_template_unclosed_html_tags(self):
        """Test validation with unclosed HTML tags."""
        # Unclosed <b> tag
        template = NotificationTemplate(
            title="Test Title",
            body_template="<b>Bold text without closing",
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) > 0
        assert any("unclosed <b> tag" in error.lower() for error in errors)

        # Unclosed <code> tag
        template = NotificationTemplate(
            title="Test Title",
            body_template="<code>Code without closing",
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) > 0
        assert any("unclosed <code> tag" in error.lower() for error in errors)

    def test_validate_template_missing_user_variables(self):
        """Test validation with missing required user variables."""
        template = NotificationTemplate(
            title="Test Title",
            body_template="Message without user info",
            include_user_info=True,
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) > 0

        # Should complain about missing user_display_name and user_id
        user_var_errors = [
            e for e in errors if "missing required user variable" in e.lower()
        ]
        assert len(user_var_errors) > 0

    def test_validate_template_missing_calculation_variables(self):
        """Test validation with missing required calculation variables."""
        template = NotificationTemplate(
            title="Test Title",
            body_template="Message without calculation info",
            include_calculation_details=True,
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) > 0

        # Should complain about missing calculation variables
        calc_var_errors = [
            e for e in errors if "missing required calculation variable" in e.lower()
        ]
        assert len(calc_var_errors) > 0

    def test_validate_template_with_user_variables_present(self):
        """Test validation passes when required user variables are present."""
        template = NotificationTemplate(
            title="Test Title",
            body_template="Hello {user_display_name}! Your ID: {user_id}",
            include_user_info=True,
            include_calculation_details=False,
        )

        errors = NotificationTemplates.validate_template(template)
        user_var_errors = [
            e for e in errors if "missing required user variable" in e.lower()
        ]
        assert len(user_var_errors) == 0

    def test_validate_template_with_calculation_variables_present(self):
        """Test validation passes when required calculation variables are present."""
        template = NotificationTemplate(
            title="Test Title",
            body_template="Pair: {currency_pair}, In: {input_amount}, Out: {output_amount}",
            include_user_info=False,
            include_calculation_details=True,
        )

        errors = NotificationTemplates.validate_template(template)
        calc_var_errors = [
            e for e in errors if "missing required calculation variable" in e.lower()
        ]
        assert len(calc_var_errors) == 0

    def test_validate_template_multiple_errors(self):
        """Test validation with multiple errors."""
        template = NotificationTemplate(
            title="",  # Empty title
            body_template="<b>Unclosed tag {unmatched_brace",  # Multiple issues
            include_user_info=True,  # But no user variables
        )

        errors = NotificationTemplates.validate_template(template)
        assert len(errors) > 1

        # Should have errors for title, HTML tag, braces, and missing variables
        error_text = " ".join(errors).lower()
        assert "title is required" in error_text
        assert "unclosed" in error_text or "unmatched" in error_text

    def test_validate_all_default_templates(self):
        """Test that all default templates are valid."""
        templates = NotificationTemplates.get_default_templates()

        for name, template in templates.items():
            errors = NotificationTemplates.validate_template(template)
            assert (
                len(errors) == 0
            ), f"Default template '{name}' has validation errors: {errors}"

    def test_template_html_formatting(self):
        """Test that templates use proper HTML formatting."""
        templates = NotificationTemplates.get_default_templates()

        for name, template in templates.items():
            body = template.body_template

            # Check for proper HTML tags
            if "<b>" in body:
                assert "</b>" in body, f"Template '{name}' has unclosed <b> tag"

            if "<code>" in body:
                assert "</code>" in body, f"Template '{name}' has unclosed <code> tag"

            # Check for emoji usage (should start with emoji)
            assert body.strip().startswith(
                ("🔔", "📊", "🧮", "⚠️", "🚨", "📈", "👨‍💼", "🔌")
            ), f"Template '{name}' should start with an appropriate emoji"

    def test_template_variable_consistency(self):
        """Test that templates use consistent variable naming."""
        templates = NotificationTemplates.get_default_templates()
        available_vars = set(NotificationTemplates.get_template_variables().keys())

        for name, template in templates.items():
            body = template.body_template

            # Extract variables from template (simple regex-like approach)
            import re

            variables_in_template = set(re.findall(r"\{(\w+)\}", body))

            # Check that all variables used in template are documented
            undocumented_vars = variables_in_template - available_vars

            # Allow some special variables that might be added dynamically
            allowed_special_vars = {
                "username_line",
                "date",
                "alert_type",
                "alert_message",
                "alert_details",
                "total_transactions",
                "successful_transactions",
                "rejected_transactions",
                "pending_transactions",
                "total_volume",
                "total_profit",
                "average_transaction",
                "top_pairs",
                "manager_activity",
                "currency_pairs",
                "assigned_by",
                "old_markup_rate",
                "new_markup_rate",
                "markup_change",
                "profit_example",
                "changed_by",
                "retry_count",
                "last_success",
            }

            undocumented_vars = undocumented_vars - allowed_special_vars

            assert (
                len(undocumented_vars) == 0
            ), f"Template '{name}' uses undocumented variables: {undocumented_vars}"
