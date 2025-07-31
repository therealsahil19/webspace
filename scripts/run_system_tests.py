#!/usr/bin/env python3
"""
Comprehensive system test runner for SpaceX Launch Tracker.
Executes all integration and validation tests and generates a detailed report.
"""
import os
import sys
import subprocess
import time
import json
import requests
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class SystemTestRunner:
    """Runs comprehensive system tests and generates reports."""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None
        self.report_file = f"test_reports/system_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Ensure report directory exists
        os.makedirs("test_reports", exist_ok=True)
    
    def check_prerequisites(self) -> Dict[str, bool]:
        """Check if all prerequisites for testing are met."""
        print("🔍 Checking prerequisites...")
        
        prerequisites = {
            "python_environment": False,
            "database_available": False,
            "redis_available": False,
            "api_server_running": False,
            "docker_services": False
        }
        
        # Check Python environment
        try:
            import pytest
            import requests
            import psutil
            prerequisites["python_environment"] = True
            print("  ✓ Python environment and dependencies available")
        except ImportError as e:
            print(f"  ✗ Missing Python dependencies: {e}")
        
        # Check database availability
        try:
            from src.database import get_database_manager
            db_manager = get_database_manager()
            with db_manager.session_scope() as session:
                session.execute("SELECT 1")
            prerequisites["database_available"] = True
            print("  ✓ Database connection available")
        except Exception as e:
            print(f"  ✗ Database not available: {e}")
        
        # Check Redis availability
        try:
            from src.cache.redis_client import RedisClient
            redis_client = RedisClient()
            if redis_client.is_connected():
                prerequisites["redis_available"] = True
                print("  ✓ Redis connection available")
            else:
                print("  ✗ Redis not available")
        except Exception as e:
            print(f"  ✗ Redis connection failed: {e}")
        
        # Check API server
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code in [200, 503]:
                prerequisites["api_server_running"] = True
                print("  ✓ API server responding")
            else:
                print(f"  ✗ API server returned status {response.status_code}")
        except Exception as e:
            print(f"  ✗ API server not responding: {e}")
        
        # Check Docker services
        try:
            result = subprocess.run(["docker", "ps"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and "postgres" in result.stdout and "redis" in result.stdout:
                prerequisites["docker_services"] = True
                print("  ✓ Docker services running")
            else:
                print("  ✗ Required Docker services not running")
        except Exception as e:
            print(f"  ✗ Docker check failed: {e}")
        
        return prerequisites
    
    def run_test_suite(self, test_file: str, test_name: str) -> Dict[str, Any]:
        """Run a specific test suite and return results."""
        print(f"\n🧪 Running {test_name}...")
        
        start_time = time.time()
        
        try:
            # Run pytest with basic reporting
            result = subprocess.run([
                "python", "-m", "pytest", 
                test_file,
                "-v",
                "--tb=short"
            ], capture_output=True, text=True, timeout=300)
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Parse results
            test_result = {
                "name": test_name,
                "file": test_file,
                "duration": duration,
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "success": result.returncode == 0,
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "tests_skipped": 0
            }
            
            # Parse pytest output for test counts
            if result.stdout:
                output_lines = result.stdout.split('\n')
                for line in output_lines:
                    if 'passed' in line or 'failed' in line or 'skipped' in line:
                        # Try to extract test counts from pytest summary
                        if '::' not in line and ('passed' in line or 'failed' in line):
                            # This is likely the summary line
                            parts = line.split()
                            for i, part in enumerate(parts):
                                if 'passed' in part and i > 0:
                                    try:
                                        test_result["tests_passed"] = int(parts[i-1])
                                    except (ValueError, IndexError):
                                        pass
                                elif 'failed' in part and i > 0:
                                    try:
                                        test_result["tests_failed"] = int(parts[i-1])
                                    except (ValueError, IndexError):
                                        pass
                                elif 'skipped' in part and i > 0:
                                    try:
                                        test_result["tests_skipped"] = int(parts[i-1])
                                    except (ValueError, IndexError):
                                        pass
                
                test_result["tests_run"] = test_result["tests_passed"] + test_result["tests_failed"] + test_result["tests_skipped"]
            
            # Print summary
            if test_result["success"]:
                print(f"  ✓ {test_name} completed successfully")
                print(f"    Duration: {duration:.2f}s")
                print(f"    Tests: {test_result['tests_passed']} passed, {test_result['tests_failed']} failed, {test_result['tests_skipped']} skipped")
            else:
                print(f"  ✗ {test_name} failed")
                print(f"    Duration: {duration:.2f}s")
                if result.stderr:
                    print(f"    Error: {result.stderr[:200]}...")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            print(f"  ⏰ {test_name} timed out after 5 minutes")
            return {
                "name": test_name,
                "file": test_file,
                "duration": 300,
                "return_code": -1,
                "success": False,
                "error": "Test suite timed out",
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "tests_skipped": 0
            }
        
        except Exception as e:
            print(f"  💥 {test_name} crashed: {e}")
            return {
                "name": test_name,
                "file": test_file,
                "duration": 0,
                "return_code": -1,
                "success": False,
                "error": str(e),
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "tests_skipped": 0
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all system tests."""
        print("🚀 Starting comprehensive system testing...")
        self.start_time = time.time()
        
        # Check prerequisites first
        prerequisites = self.check_prerequisites()
        
        # Define test suites
        test_suites = [
            ("tests/test_system_integration.py", "System Integration Tests"),
            ("tests/test_system_validation.py", "System Validation Tests"),
            ("tests/test_end_to_end.py", "End-to-End Tests"),
            ("tests/test_performance.py", "Performance Tests"),
        ]
        
        # Run each test suite
        results = {}
        for test_file, test_name in test_suites:
            if os.path.exists(test_file):
                results[test_name] = self.run_test_suite(test_file, test_name)
            else:
                print(f"  ⚠️  Test file not found: {test_file}")
                results[test_name] = {
                    "name": test_name,
                    "file": test_file,
                    "success": False,
                    "error": "Test file not found",
                    "tests_run": 0,
                    "tests_passed": 0,
                    "tests_failed": 0,
                    "tests_skipped": 0
                }
        
        self.end_time = time.time()
        
        # Compile overall results
        overall_results = {
            "timestamp": datetime.now().isoformat(),
            "duration": self.end_time - self.start_time,
            "prerequisites": prerequisites,
            "test_suites": results,
            "summary": self._calculate_summary(results)
        }
        
        self.test_results = overall_results
        return overall_results
    
    def _calculate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall test summary."""
        total_suites = len(results)
        successful_suites = sum(1 for r in results.values() if r["success"])
        
        total_tests = sum(r["tests_run"] for r in results.values())
        total_passed = sum(r["tests_passed"] for r in results.values())
        total_failed = sum(r["tests_failed"] for r in results.values())
        total_skipped = sum(r["tests_skipped"] for r in results.values())
        
        return {
            "total_suites": total_suites,
            "successful_suites": successful_suites,
            "failed_suites": total_suites - successful_suites,
            "suite_success_rate": successful_suites / total_suites if total_suites > 0 else 0,
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "test_success_rate": total_passed / total_tests if total_tests > 0 else 0
        }
    
    def generate_report(self) -> str:
        """Generate a comprehensive test report."""
        if not self.test_results:
            return "No test results available"
        
        # Save JSON report
        with open(self.report_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        # Generate text report
        report = []
        report.append("=" * 80)
        report.append("SPACEX LAUNCH TRACKER - SYSTEM TEST REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {self.test_results['timestamp']}")
        report.append(f"Duration: {self.test_results['duration']:.2f} seconds")
        report.append("")
        
        # Prerequisites section
        report.append("PREREQUISITES")
        report.append("-" * 40)
        for prereq, status in self.test_results['prerequisites'].items():
            status_icon = "✓" if status else "✗"
            report.append(f"{status_icon} {prereq.replace('_', ' ').title()}")
        report.append("")
        
        # Test suites section
        report.append("TEST SUITES")
        report.append("-" * 40)
        for suite_name, suite_result in self.test_results['test_suites'].items():
            status_icon = "✓" if suite_result["success"] else "✗"
            report.append(f"{status_icon} {suite_name}")
            report.append(f"    Duration: {suite_result.get('duration', 0):.2f}s")
            report.append(f"    Tests: {suite_result['tests_passed']} passed, "
                         f"{suite_result['tests_failed']} failed, "
                         f"{suite_result['tests_skipped']} skipped")
            
            if not suite_result["success"] and suite_result.get("error"):
                report.append(f"    Error: {suite_result['error']}")
            report.append("")
        
        # Summary section
        summary = self.test_results['summary']
        report.append("SUMMARY")
        report.append("-" * 40)
        report.append(f"Test Suites: {summary['successful_suites']}/{summary['total_suites']} successful "
                     f"({summary['suite_success_rate']:.1%})")
        report.append(f"Individual Tests: {summary['total_passed']}/{summary['total_tests']} passed "
                     f"({summary['test_success_rate']:.1%})")
        report.append(f"Failed: {summary['total_failed']}, Skipped: {summary['total_skipped']}")
        report.append("")
        
        # Overall status
        overall_success = summary['suite_success_rate'] >= 0.8 and summary['test_success_rate'] >= 0.8
        report.append("OVERALL STATUS")
        report.append("-" * 40)
        if overall_success:
            report.append("🎉 SYSTEM VALIDATION PASSED")
            report.append("The SpaceX Launch Tracker system meets all requirements and is ready for deployment.")
        else:
            report.append("❌ SYSTEM VALIDATION FAILED")
            report.append("The system has issues that need to be addressed before deployment.")
        
        report.append("")
        report.append(f"Detailed JSON report saved to: {self.report_file}")
        report.append("=" * 80)
        
        report_text = "\n".join(report)
        
        # Save text report
        text_report_file = self.report_file.replace('.json', '.txt')
        with open(text_report_file, 'w', encoding='utf-8') as f:
            f.write(report_text)
        
        return report_text
    
    def run_performance_benchmarks(self) -> Dict[str, Any]:
        """Run specific performance benchmarks."""
        print("\n⚡ Running performance benchmarks...")
        
        benchmarks = {}
        
        # API response time benchmark
        try:
            import requests
            start_time = time.time()
            response = requests.get("http://localhost:8000/api/launches?limit=10", timeout=5)
            end_time = time.time()
            
            benchmarks["api_response_time"] = {
                "duration": end_time - start_time,
                "success": response.status_code == 200,
                "meets_requirement": (end_time - start_time) < 1.0
            }
            
            print(f"  API Response Time: {benchmarks['api_response_time']['duration']:.3f}s")
            
        except Exception as e:
            benchmarks["api_response_time"] = {
                "error": str(e),
                "success": False,
                "meets_requirement": False
            }
        
        # Database query benchmark
        try:
            from src.database import get_database_manager
            from src.models.launch import Launch
            
            db_manager = get_database_manager()
            with db_manager.session_scope() as session:
                start_time = time.time()
                launches = session.query(Launch).limit(50).all()
                end_time = time.time()
                
                benchmarks["database_query"] = {
                    "duration": end_time - start_time,
                    "records_retrieved": len(launches),
                    "success": True,
                    "meets_requirement": (end_time - start_time) < 0.1
                }
                
                print(f"  Database Query: {benchmarks['database_query']['duration']:.3f}s for {len(launches)} records")
                
        except Exception as e:
            benchmarks["database_query"] = {
                "error": str(e),
                "success": False,
                "meets_requirement": False
            }
        
        # Cache performance benchmark
        try:
            from src.cache.cache_manager import CacheManager
            
            cache_manager = CacheManager()
            if cache_manager.is_enabled():
                test_data = {"test": "data", "timestamp": time.time()}
                
                # Write benchmark
                start_time = time.time()
                cache_manager.set_launch_detail("benchmark-test", test_data)
                write_time = time.time() - start_time
                
                # Read benchmark
                start_time = time.time()
                cached_data = cache_manager.get_launch_detail("benchmark-test")
                read_time = time.time() - start_time
                
                benchmarks["cache_performance"] = {
                    "write_time": write_time,
                    "read_time": read_time,
                    "success": cached_data == test_data,
                    "meets_requirement": write_time < 0.01 and read_time < 0.005
                }
                
                # Cleanup
                cache_manager.invalidate_launch_detail("benchmark-test")
                
                print(f"  Cache Performance: {write_time:.4f}s write, {read_time:.4f}s read")
            else:
                benchmarks["cache_performance"] = {
                    "error": "Redis not available",
                    "success": False,
                    "meets_requirement": False
                }
                
        except Exception as e:
            benchmarks["cache_performance"] = {
                "error": str(e),
                "success": False,
                "meets_requirement": False
            }
        
        return benchmarks


def main():
    """Main function to run system tests."""
    runner = SystemTestRunner()
    
    print("🔬 SpaceX Launch Tracker - Comprehensive System Testing")
    print("=" * 60)
    
    # Run all tests
    results = runner.run_all_tests()
    
    # Run performance benchmarks
    benchmarks = runner.run_performance_benchmarks()
    results["benchmarks"] = benchmarks
    
    # Generate and display report
    report = runner.generate_report()
    print("\n" + report)
    
    # Exit with appropriate code
    summary = results["summary"]
    overall_success = summary['suite_success_rate'] >= 0.8 and summary['test_success_rate'] >= 0.8
    
    if overall_success:
        print("\n🎉 All system tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ System tests failed. Please review the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()