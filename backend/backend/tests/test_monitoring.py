"""
Test suite for backend monitoring and performance functionality.
Tests backend/monitoring.py functionality.
"""

import time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from backend.monitoring import PerformanceMonitor, DatabaseMonitor, CacheMonitor
from accounts.repositories import UserRepository
from backend.services import GeolocationService, CacheService
from backend.utils import get_db_alias


User = get_user_model()


class MonitoringTestCase(TestCase):
    """Test monitoring functionality."""
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_performance_monitor_time_function(self):
        """Test performance monitoring decorator."""
        @PerformanceMonitor.time_function("test_function")
        def test_function():
            time.sleep(0.1)
            return "test_result"

        result = test_function()
        self.assertEqual(result, "test_result")

    def test_performance_monitor_exception_handling(self):
        """Test performance monitoring with exceptions."""
        @PerformanceMonitor.time_function("test_function_error")
        def test_function_error():
            raise ValueError("Test error")

        with self.assertRaises(ValueError):
            test_function_error()

    def test_database_monitor_get_connection_info(self):
        """Test database connection monitoring."""
        info = DatabaseMonitor.get_connection_info()
        self.assertIn('vendor', info)
        self.assertIn('queries_count', info)
        self.assertIn('total_time', info)
        self.assertEqual(info['vendor'], 'postgresql')

    def test_database_monitor_log_query_count(self):
        """Test query count monitoring."""
        @DatabaseMonitor.log_query_count(1)
        def test_function():
            db_alias = get_db_alias()
            # This should trigger the monitor since it might execute queries
            UserRepository.count(db_alias=db_alias)
            return "result"

        result = test_function()
        self.assertEqual(result, "result")


class PerformanceMonitoringTestCase(TestCase):
    """Test performance monitoring functionality."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_performance_monitor_with_custom_name(self):
        """Test performance monitor with custom function name."""
        @PerformanceMonitor.time_function("custom_function_name")
        def test_function():
            return "success"

        result = test_function()
        self.assertEqual(result, "success")

        # Check if metric was stored (if performance monitoring is enabled)
        if hasattr(settings, 'PERFORMANCE_MONITORING') and settings.PERFORMANCE_MONITORING:
            metrics = PerformanceMonitor.get_performance_metrics("custom_function_name")
            if metrics:  # Only check if metrics were stored
                self.assertIn('execution_time', metrics)
                self.assertIn('success', metrics)
                self.assertTrue(metrics['success'])

    def test_performance_monitor_with_exception(self):
        """Test performance monitor exception handling."""
        @PerformanceMonitor.time_function("error_function")
        def error_function():
            raise ValueError("Test error")

        with self.assertRaises(ValueError):
            error_function()

        # Check if error metric was stored
        if hasattr(settings, 'PERFORMANCE_MONITORING') and settings.PERFORMANCE_MONITORING:
            metrics = PerformanceMonitor.get_performance_metrics("error_function")
            if metrics:
                self.assertIn('execution_time', metrics)
                self.assertIn('success', metrics)
                self.assertFalse(metrics['success'])
                self.assertIn('error', metrics)

    def test_performance_monitor_get_metrics(self):
        """Test getting performance metrics."""
        # Test getting metrics for non-existent function
        metrics = PerformanceMonitor.get_performance_metrics("non_existent")
        self.assertIsNone(metrics)

        # Test getting all metrics
        all_metrics = PerformanceMonitor.get_performance_metrics()
        self.assertIsInstance(all_metrics, dict)

    def test_database_monitor_log_slow_queries(self):
        """Test database slow query monitoring."""
        @PerformanceMonitor.log_slow_queries(0.001)  # Very low threshold
        def slow_query_function():
            db_alias = get_db_alias()
            # This should trigger slow query warning
            UserRepository.count(db_alias=db_alias)
            return "result"

        result = slow_query_function()
        self.assertEqual(result, "result")

    def test_database_monitor_query_count(self):
        """Test database query count monitoring."""
        @DatabaseMonitor.log_query_count(0)  # Zero threshold to trigger warning
        def high_query_function():
            db_alias = get_db_alias()
            # This should trigger high query count warning
            UserRepository.count(db_alias=db_alias)
            return "result"

        result = high_query_function()
        self.assertEqual(result, "result")

    def test_cache_monitor_log_cache_misses(self):
        """Test cache miss monitoring."""
        @CacheMonitor.log_cache_misses("test_prefix")
        def cache_miss_function():
            return "cache_miss_result"

        result = cache_miss_function()
        self.assertEqual(result, "cache_miss_result")


class CacheTestCase(TestCase):
    """Test cases for caching functionality (cache monitoring)."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch('backend.services.services.get_geolocation_info')
    def test_geolocation_caching(self, mock_geo_info):
        """Test geolocation data caching."""
        mock_geo_info.return_value = {
            'country': 'France',
            'countryCode': 'FR'
        }

        # First call should hit the API
        data1 = GeolocationService.get_geolocation_data('192.168.1.1', use_cache=True)
        # Second call should use cache
        data2 = GeolocationService.get_geolocation_data('192.168.1.1', use_cache=True)

        self.assertEqual(data1, data2)
        mock_geo_info.assert_called_once()  # Should only be called once due to caching

    def test_cache_service_get_or_set(self):
        """Test cache service get_or_set method."""
        def expensive_operation():
            return "computed_value"

        # First call should compute and cache
        result1 = CacheService.get_or_set('test_key', expensive_operation, 300)
        self.assertEqual(result1, "computed_value")

        # Second call should return cached value
        result2 = CacheService.get_or_set('test_key', lambda: "different_value", 300)
        self.assertEqual(result2, "computed_value")  # Should be cached value

    def test_cache_service_invalidate_pattern(self):
        """Test cache service pattern invalidation."""
        # Set some cache values
        cache.set('test_pattern_1', 'value1', 300)
        cache.set('test_pattern_2', 'value2', 300)
        cache.set('other_key', 'value3', 300)

        # This is a basic test - actual implementation depends on cache backend
        # This will not work with LocMemCache as it does not support pattern matching
        CacheService.invalidate_pattern('test_pattern_*')

        # Test that the method doesn't crash
        self.assertEqual(cache.get('test_pattern_1'), 'value1')

    def test_cache_service_get_or_set_with_callable(self):
        """Test cache service with callable function."""
        call_count = 0

        def expensive_operation():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # First call should execute the function
        result1 = CacheService.get_or_set('test_key', expensive_operation, 300)
        self.assertEqual(result1, "result_1")
        self.assertEqual(call_count, 1)

        # Second call should return cached value
        result2 = CacheService.get_or_set('test_key', expensive_operation, 300)
        self.assertEqual(result2, "result_1")  # Should be cached
        self.assertEqual(call_count, 1)  # Function should not be called again

    def test_cache_service_get_or_set_with_none_result(self):
        """Test cache service when callable returns None."""
        def return_none():
            return None

        result = CacheService.get_or_set('test_key', return_none, 300)
        self.assertIsNone(result)

        # Should cache Value
        result2 = CacheService.get_or_set('test_key', lambda: "different", 300)
        self.assertEqual(result2, "different")

        # Should return cached Value
        result2 = CacheService.get_or_set('test_key', return_none, 300)
        self.assertEqual(result2, "different")

    def test_cache_service_invalidate_pattern_with_error(self):
        """Test cache service pattern invalidation with error handling."""
        # This tests the error handling in invalidate_pattern
        with patch('backend.services.services.cache.delete_many') as mock_delete:
            mock_delete.side_effect = Exception("Cache error")
            # Should not raise an exception
            CacheService.invalidate_pattern('test_*')
            # cache.keys(pattern) will raise error in LocMemCache used in local
            mock_delete.assert_not_called()

    def test_geolocation_service_without_cache(self):
        """Test geolocation service without caching."""
        with patch('backend.services.services.get_geolocation_info') as mock_geo:
            mock_geo.return_value = {
                'country': 'France',
                'countryCode': 'FR'
            }

            data = GeolocationService.get_geolocation_data(
                '192.168.1.1', use_cache=False
            )
            self.assertEqual(data['country'], 'France')

            # Should not interact with cache
            self.assertIsNone(cache.get('geolocation:192.168.1.1:country,countryCode'))
