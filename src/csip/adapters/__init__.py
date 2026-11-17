"""Acquisition adapters.

Adapters implement ``application.ports.acquisition.AcquisitionAdapterPort``.
Every adapter receives a policy-approved ``AcquisitionPlan``; none can act
without one. Source-specific selectors/navigation stay in adapters.
"""
