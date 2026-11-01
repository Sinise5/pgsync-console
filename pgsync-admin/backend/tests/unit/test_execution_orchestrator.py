"""Unit tests for execution orchestrator."""

import pytest
from backend.services.execution_orchestrator import ExecutionOrchestrator


class TestExecutionOrchestrator:
    """Test execution orchestration."""

    def test_orchestrator_init(self):
        """Test orchestrator initialization."""
        orchestrator = ExecutionOrchestrator()
        assert orchestrator is not None
        assert len(orchestrator.processes) == 0

    def test_stop_nonexistent_process(self):
        """Test stopping non-existent process."""
        orchestrator = ExecutionOrchestrator()
        result = orchestrator.stop_process(9999)
        assert result is False

    def test_get_status_nonexistent(self):
        """Test getting status of non-existent process."""
        orchestrator = ExecutionOrchestrator()
        status = orchestrator.get_process_status(9999)
        assert status is None

    def test_get_process_info_invalid_pid(self):
        """Test getting info for invalid PID."""
        orchestrator = ExecutionOrchestrator()
        info = orchestrator.get_process_info(999999)
        assert info is None
