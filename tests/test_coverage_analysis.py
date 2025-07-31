"""
Test coverage analysis and reporting.
Analyzes test coverage across all components and generates reports.
"""
import pytest
import subprocess
import json
import os
import sys
from pathlib import Path
import coverage
from datetime import datetime


class TestCoverageAnalysis:
    """Test coverage analysis and reporting."""
    
    def test_backend_test_coverage(self):
        """Test backend code coverage and ensure >80% coverage."""
        # Initialize coverage
        cov = coverage.Coverage(
            source=['src'],
            omit=[
                '*/tests/*',
                '*/test_*',
                '*/__pycache__/*',
                '*/venv/*',
                '*/migrations/*'
            ]
        )
        
        # Start coverage measurement
        cov.start()
        
        try:
            # Run all backend tests
            result = subprocess.run([
                sys.executable, '-m', 'pytest', 
                'tests/', 
                '-v',
                '--tb=short',
                '-x'  # Stop on first failure for coverage analysis
            ], capture_output=True, text=True, cwd='.')
            
            # Stop coverage measurement
            cov.stop()
            cov.save()
            
            # Generate coverage report
            coverage_report = self._generate_coverage_report(cov)
            
            # Assert minimum coverage
            total_coverage = coverage_report['total_coverage']
            assert total_coverage >= 80.0, f"Coverage too low: {total_coverage:.1f}% (minimum: 80%)"
            
            print(f"Backend test coverage: {total_coverage:.1f}%")
            
            # Check individual module coverage
            low_coverage_modules = [
                module for module, data in coverage_report['modules'].items()
                if data['coverage'] < 70.0 and data['statements'] > 10
            ]
            
            if low_coverage_modules:
                print("Modules with low coverage:")
                for module in low_coverage_modules:
                    module_data = coverage_report['modules'][module]
                    print(f"  {module}: {module_data['coverage']:.1f}%")
            
            return coverage_report
            
        except Exception as e:
            cov.stop()
            raise e
    
    def test_frontend_test_coverage(self):
        """Test frontend code coverage."""
        frontend_path = Path('frontend')
        
        if not frontend_path.exists():
            pytest.skip("Frontend directory not found")
        
        # Run frontend tests with coverage
        result = subprocess.run([
            'npm', 'run', 'test', '--', '--coverage', '--watchAll=false'
        ], capture_output=True, text=True, cwd=frontend_path)
        
        if result.returncode != 0:
            print(f"Frontend tests failed: {result.stderr}")
            pytest.fail("Frontend tests failed")
        
        # Parse coverage from output
        coverage_info = self._parse_frontend_coverage(result.stdout)
        
        if coverage_info:
            total_coverage = coverage_info.get('total', 0)
            assert total_coverage >= 80.0, f"Frontend coverage too low: {total_coverage:.1f}%"
            print(f"Frontend test coverage: {total_coverage:.1f}%")
        else:
            print("Could not parse frontend coverage information")
    
    def test_integration_test_coverage(self):
        """Test integration test coverage specifically."""
        # Run only integration tests
        integration_tests = [
            'tests/test_end_to_end.py',
            'tests/test_api_performance.py',
            'tests/test_database_migrations.py',
            'tests/test_data_pipeline.py'
        ]
        
        existing_tests = [test for test in integration_tests if os.path.exists(test)]
        
        if not existing_tests:
            pytest.skip("No integration tests found")
        
        # Initialize coverage for integration tests
        cov = coverage.Coverage(
            source=['src'],
            omit=['*/tests/*', '*/__pycache__/*']
        )
        
        cov.start()
        
        try:
            # Run integration tests
            result = subprocess.run([
                sys.executable, '-m', 'pytest'
            ] + existing_tests + ['-v'], capture_output=True, text=True)
            
            cov.stop()
            cov.save()
            
            # Generate integration coverage report
            integration_coverage = self._generate_coverage_report(cov)
            
            print(f"Integration test coverage: {integration_coverage['total_coverage']:.1f}%")
            
            # Integration tests should cover critical paths
            critical_modules = [
                'src.api',
                'src.scraping',
                'src.processing',
                'src.database'
            ]
            
            for module in critical_modules:
                if module in integration_coverage['modules']:
                    module_coverage = integration_coverage['modules'][module]['coverage']
                    print(f"  {module}: {module_coverage:.1f}%")
            
            return integration_coverage
            
        except Exception as e:
            cov.stop()
            raise e
    
    def test_generate_comprehensive_coverage_report(self):
        """Generate comprehensive coverage report."""
        # Run all tests with coverage
        cov = coverage.Coverage(
            source=['src'],
            omit=[
                '*/tests/*',
                '*/test_*',
                '*/__pycache__/*',
                '*/venv/*',
                '*/migrations/*',
                '*/alembic/*'
            ]
        )
        
        cov.start()
        
        try:
            # Run all backend tests
            subprocess.run([
                sys.executable, '-m', 'pytest', 
                'tests/', 
                '-v',
                '--tb=short'
            ], cwd='.')
            
            cov.stop()
            cov.save()
            
            # Generate detailed report
            report_data = self._generate_detailed_coverage_report(cov)
            
            # Save report to file
            report_file = 'coverage_report.json'
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)
            
            print(f"Comprehensive coverage report saved to {report_file}")
            
            # Generate HTML report
            try:
                cov.html_report(directory='htmlcov')
                print("HTML coverage report generated in htmlcov/")
            except Exception as e:
                print(f"Could not generate HTML report: {e}")
            
            return report_data
            
        except Exception as e:
            cov.stop()
            raise e
    
    def _generate_coverage_report(self, cov):
        """Generate coverage report from coverage object."""
        # Get coverage data
        cov.get_data()
        
        # Calculate total coverage
        total_statements = 0
        total_missing = 0
        modules = {}
        
        for filename in cov.get_data().measured_files():
            if 'tests' in filename or '__pycache__' in filename:
                continue
                
            analysis = cov.analysis2(filename)
            statements = len(analysis[1])
            missing = len(analysis[3])
            covered = statements - missing
            
            if statements > 0:
                coverage_percent = (covered / statements) * 100
                
                # Convert filename to module name
                module_name = filename.replace('/', '.').replace('\\', '.').replace('.py', '')
                if module_name.startswith('.'):
                    module_name = module_name[1:]
                
                modules[module_name] = {
                    'statements': statements,
                    'missing': missing,
                    'covered': covered,
                    'coverage': coverage_percent
                }
                
                total_statements += statements
                total_missing += missing
        
        total_coverage = ((total_statements - total_missing) / total_statements * 100) if total_statements > 0 else 0
        
        return {
            'total_coverage': total_coverage,
            'total_statements': total_statements,
            'total_missing': total_missing,
            'modules': modules
        }
    
    def _generate_detailed_coverage_report(self, cov):
        """Generate detailed coverage report with additional metrics."""
        basic_report = self._generate_coverage_report(cov)
        
        # Add additional metrics
        detailed_report = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_coverage': basic_report['total_coverage'],
                'total_statements': basic_report['total_statements'],
                'total_missing': basic_report['total_missing'],
                'modules_count': len(basic_report['modules'])
            },
            'modules': basic_report['modules'],
            'coverage_by_category': self._categorize_coverage(basic_report['modules']),
            'recommendations': self._generate_coverage_recommendations(basic_report['modules'])
        }
        
        return detailed_report
    
    def _categorize_coverage(self, modules):
        """Categorize modules by coverage level."""
        categories = {
            'excellent': [],  # >90%
            'good': [],       # 80-90%
            'fair': [],       # 60-80%
            'poor': []        # <60%
        }
        
        for module, data in modules.items():
            coverage = data['coverage']
            if coverage >= 90:
                categories['excellent'].append(module)
            elif coverage >= 80:
                categories['good'].append(module)
            elif coverage >= 60:
                categories['fair'].append(module)
            else:
                categories['poor'].append(module)
        
        return categories
    
    def _generate_coverage_recommendations(self, modules):
        """Generate recommendations for improving coverage."""
        recommendations = []
        
        # Find modules with low coverage and significant code
        low_coverage_modules = [
            (module, data) for module, data in modules.items()
            if data['coverage'] < 80 and data['statements'] > 20
        ]
        
        if low_coverage_modules:
            recommendations.append({
                'type': 'low_coverage',
                'message': 'The following modules have low coverage and significant code:',
                'modules': [
                    f"{module}: {data['coverage']:.1f}% ({data['missing']} uncovered statements)"
                    for module, data in low_coverage_modules
                ]
            })
        
        # Find modules with no coverage
        no_coverage_modules = [
            module for module, data in modules.items()
            if data['coverage'] == 0 and data['statements'] > 5
        ]
        
        if no_coverage_modules:
            recommendations.append({
                'type': 'no_coverage',
                'message': 'The following modules have no test coverage:',
                'modules': no_coverage_modules
            })
        
        # Check for missing critical path coverage
        critical_paths = ['src.api', 'src.scraping', 'src.processing', 'src.database']
        missing_critical = []
        
        for path in critical_paths:
            path_modules = [m for m in modules.keys() if m.startswith(path)]
            if not path_modules:
                missing_critical.append(path)
            else:
                avg_coverage = sum(modules[m]['coverage'] for m in path_modules) / len(path_modules)
                if avg_coverage < 70:
                    missing_critical.append(f"{path} (avg: {avg_coverage:.1f}%)")
        
        if missing_critical:
            recommendations.append({
                'type': 'critical_paths',
                'message': 'Critical paths with insufficient coverage:',
                'modules': missing_critical
            })
        
        return recommendations
    
    def _parse_frontend_coverage(self, output):
        """Parse frontend coverage from Jest output."""
        lines = output.split('\n')
        coverage_info = {}
        
        # Look for coverage summary
        in_coverage_section = False
        for line in lines:
            if 'Coverage summary' in line:
                in_coverage_section = True
                continue
            
            if in_coverage_section and '%' in line:
                # Parse coverage line (format varies)
                if 'All files' in line:
                    # Extract total coverage percentage
                    parts = line.split()
                    for part in parts:
                        if part.endswith('%'):
                            try:
                                coverage_info['total'] = float(part.rstrip('%'))
                                break
                            except ValueError:
                                continue
        
        return coverage_info
    
    def test_test_quality_metrics(self):
        """Analyze test quality metrics."""
        test_files = []
        for root, dirs, files in os.walk('tests'):
            for file in files:
                if file.startswith('test_') and file.endswith('.py'):
                    test_files.append(os.path.join(root, file))
        
        metrics = {
            'total_test_files': len(test_files),
            'total_test_functions': 0,
            'test_files_analysis': []
        }
        
        for test_file in test_files:
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Count test functions
                test_functions = content.count('def test_')
                test_classes = content.count('class Test')
                
                file_metrics = {
                    'file': test_file,
                    'test_functions': test_functions,
                    'test_classes': test_classes,
                    'lines': len(content.split('\n')),
                    'has_fixtures': '@pytest.fixture' in content,
                    'has_parametrize': '@pytest.mark.parametrize' in content,
                    'has_async_tests': '@pytest.mark.asyncio' in content
                }
                
                metrics['test_files_analysis'].append(file_metrics)
                metrics['total_test_functions'] += test_functions
                
            except Exception as e:
                print(f"Error analyzing {test_file}: {e}")
        
        # Quality assertions
        assert metrics['total_test_functions'] >= 50, \
            f"Not enough test functions: {metrics['total_test_functions']} (minimum: 50)"
        
        # Check for test distribution
        files_with_tests = [f for f in metrics['test_files_analysis'] if f['test_functions'] > 0]
        assert len(files_with_tests) >= 10, \
            f"Not enough test files with tests: {len(files_with_tests)} (minimum: 10)"
        
        print(f"Test quality metrics:")
        print(f"  Total test files: {metrics['total_test_files']}")
        print(f"  Total test functions: {metrics['total_test_functions']}")
        print(f"  Files with fixtures: {sum(1 for f in metrics['test_files_analysis'] if f['has_fixtures'])}")
        print(f"  Files with parametrized tests: {sum(1 for f in metrics['test_files_analysis'] if f['has_parametrize'])}")
        print(f"  Files with async tests: {sum(1 for f in metrics['test_files_analysis'] if f['has_async_tests'])}")
        
        return metrics


class TestContinuousIntegration:
    """Test CI/CD pipeline integration."""
    
    def test_ci_test_configuration(self):
        """Test CI configuration for automated testing."""
        # Check for CI configuration files
        ci_files = [
            '.github/workflows/test.yml',
            '.github/workflows/ci.yml',
            'Jenkinsfile',
            '.gitlab-ci.yml',
            '.travis.yml'
        ]
        
        found_ci_config = any(os.path.exists(ci_file) for ci_file in ci_files)
        
        if not found_ci_config:
            print("Warning: No CI configuration found. Consider adding automated testing.")
        
        # Check for test requirements
        if os.path.exists('requirements.txt'):
            with open('requirements.txt', 'r') as f:
                requirements = f.read()
                
            test_packages = ['pytest', 'coverage', 'playwright']
            missing_packages = [pkg for pkg in test_packages if pkg not in requirements]
            
            if missing_packages:
                print(f"Warning: Missing test packages in requirements.txt: {missing_packages}")
        
        # Check for test scripts
        if os.path.exists('package.json'):
            with open('package.json', 'r') as f:
                package_data = json.load(f)
                
            scripts = package_data.get('scripts', {})
            if 'test' not in scripts:
                print("Warning: No test script found in package.json")
    
    def test_test_environment_setup(self):
        """Test that test environment can be set up correctly."""
        # Check Python environment
        python_version = sys.version_info
        assert python_version >= (3, 8), f"Python version too old: {python_version}"
        
        # Check required packages
        required_packages = [
            'pytest',
            'coverage',
            'playwright',
            'fastapi',
            'sqlalchemy'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"Warning: Missing required packages: {missing_packages}")
        
        # Check database connectivity
        try:
            from src.database import get_database_manager
            db_manager = get_database_manager()
            with db_manager.session_scope() as session:
                session.execute("SELECT 1")
            print("Database connectivity: ✓")
        except Exception as e:
            print(f"Database connectivity issue: {e}")
        
        # Check Redis connectivity (if available)
        try:
            from src.cache.redis_client import RedisClient
            redis_client = RedisClient()
            if redis_client.is_connected():
                print("Redis connectivity: ✓")
            else:
                print("Redis connectivity: ✗ (optional)")
        except Exception as e:
            print(f"Redis connectivity issue: {e} (optional)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])