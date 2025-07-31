#!/usr/bin/env python3
"""
Simple system validation script for SpaceX Launch Tracker.
Validates the system without requiring all dependencies to be installed.
"""
import os
import sys
import subprocess
import time
import json
from datetime import datetime
from pathlib import Path


def check_file_exists(file_path: str, description: str) -> bool:
    """Check if a file exists."""
    exists = os.path.exists(file_path)
    status = "✓" if exists else "✗"
    print(f"  {status} {description}: {file_path}")
    return exists


def check_directory_structure() -> dict:
    """Check that all required directories and files exist."""
    print("📁 Checking directory structure...")
    
    checks = {
        "src_directory": check_file_exists("src/", "Source directory"),
        "tests_directory": check_file_exists("tests/", "Tests directory"),
        "frontend_directory": check_file_exists("frontend/", "Frontend directory"),
        "docs_directory": check_file_exists("docs/", "Documentation directory"),
        "scripts_directory": check_file_exists("scripts/", "Scripts directory"),
        
        # Key source files
        "main_api": check_file_exists("src/main.py", "Main API file"),
        "database_config": check_file_exists("src/database.py", "Database configuration"),
        "celery_app": check_file_exists("src/celery_app.py", "Celery application"),
        
        # Frontend files
        "package_json": check_file_exists("frontend/package.json", "Frontend package.json"),
        "next_config": check_file_exists("frontend/next.config.ts", "Next.js configuration"),
        
        # Docker files
        "docker_compose": check_file_exists("docker-compose.yml", "Docker Compose development"),
        "docker_compose_prod": check_file_exists("docker-compose.prod.yml", "Docker Compose production"),
        "dockerfile_backend": check_file_exists("Dockerfile.backend", "Backend Dockerfile"),
        "dockerfile_frontend": check_file_exists("Dockerfile.frontend", "Frontend Dockerfile"),
        
        # Configuration files
        "env_example": check_file_exists(".env.example", "Environment example"),
        "env_prod_example": check_file_exists(".env.production.example", "Production environment example"),
        "alembic_ini": check_file_exists("alembic.ini", "Alembic configuration"),
        
        # Documentation
        "readme_deployment": check_file_exists("README.deployment.md", "Deployment README"),
        "operational_procedures": check_file_exists("docs/operational_procedures.md", "Operational procedures"),
        
        # Test files
        "test_integration": check_file_exists("tests/test_system_integration.py", "System integration tests"),
        "test_validation": check_file_exists("tests/test_system_validation.py", "System validation tests"),
        "test_end_to_end": check_file_exists("tests/test_end_to_end.py", "End-to-end tests"),
        
        # Scripts
        "deploy_script": check_file_exists("scripts/deploy.py", "Deployment script"),
        "migrate_script": check_file_exists("scripts/migrate.py", "Migration script"),
        "system_test_script": check_file_exists("scripts/run_system_tests.py", "System test runner"),
    }
    
    passed = sum(1 for result in checks.values() if result)
    total = len(checks)
    print(f"\n📊 Directory structure: {passed}/{total} checks passed ({passed/total:.1%})")
    
    return checks


def check_python_syntax() -> dict:
    """Check Python files for syntax errors."""
    print("\n🐍 Checking Python syntax...")
    
    python_files = []
    
    # Find Python files
    for root, dirs, files in os.walk("."):
        # Skip certain directories
        if any(skip in root for skip in [".git", "__pycache__", "node_modules", "venv", ".venv"]):
            continue
            
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
    
    syntax_checks = {}
    
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                compile(f.read(), file_path, 'exec')
            syntax_checks[file_path] = True
            print(f"  ✓ {file_path}")
        except SyntaxError as e:
            syntax_checks[file_path] = False
            print(f"  ✗ {file_path}: {e}")
        except Exception as e:
            syntax_checks[file_path] = False
            print(f"  ⚠ {file_path}: {e}")
    
    passed = sum(1 for result in syntax_checks.values() if result)
    total = len(syntax_checks)
    print(f"\n📊 Python syntax: {passed}/{total} files passed ({passed/total:.1%})")
    
    return syntax_checks


def check_configuration_files() -> dict:
    """Check configuration files for completeness."""
    print("\n⚙️ Checking configuration files...")
    
    checks = {}
    
    # Check .env.example
    if os.path.exists(".env.example"):
        with open(".env.example", 'r') as f:
            env_content = f.read()
        
        required_vars = [
            "DATABASE_URL", "REDIS_URL", "JWT_SECRET_KEY", 
            "ADMIN_USERNAME", "ADMIN_PASSWORD", "CELERY_BROKER_URL"
        ]
        
        missing_vars = [var for var in required_vars if var not in env_content]
        
        if not missing_vars:
            checks["env_example_complete"] = True
            print("  ✓ .env.example contains all required variables")
        else:
            checks["env_example_complete"] = False
            print(f"  ✗ .env.example missing variables: {', '.join(missing_vars)}")
    else:
        checks["env_example_complete"] = False
        print("  ✗ .env.example not found")
    
    # Check docker-compose.yml
    if os.path.exists("docker-compose.yml"):
        with open("docker-compose.yml", 'r') as f:
            compose_content = f.read()
        
        required_services = ["postgres", "redis", "backend", "frontend", "celery-worker"]
        missing_services = [svc for svc in required_services if svc not in compose_content]
        
        if not missing_services:
            checks["compose_services_complete"] = True
            print("  ✓ docker-compose.yml contains all required services")
        else:
            checks["compose_services_complete"] = False
            print(f"  ✗ docker-compose.yml missing services: {', '.join(missing_services)}")
    else:
        checks["compose_services_complete"] = False
        print("  ✗ docker-compose.yml not found")
    
    # Check package.json
    if os.path.exists("frontend/package.json"):
        try:
            with open("frontend/package.json", 'r') as f:
                package_data = json.load(f)
            
            required_deps = ["next", "react", "typescript"]
            dependencies = {**package_data.get("dependencies", {}), **package_data.get("devDependencies", {})}
            missing_deps = [dep for dep in required_deps if dep not in dependencies]
            
            if not missing_deps:
                checks["frontend_deps_complete"] = True
                print("  ✓ Frontend package.json contains required dependencies")
            else:
                checks["frontend_deps_complete"] = False
                print(f"  ✗ Frontend package.json missing dependencies: {', '.join(missing_deps)}")
        except json.JSONDecodeError:
            checks["frontend_deps_complete"] = False
            print("  ✗ Frontend package.json is invalid JSON")
    else:
        checks["frontend_deps_complete"] = False
        print("  ✗ Frontend package.json not found")
    
    passed = sum(1 for result in checks.values() if result)
    total = len(checks)
    print(f"\n📊 Configuration: {passed}/{total} checks passed ({passed/total:.1%})")
    
    return checks


def check_test_coverage() -> dict:
    """Check test file coverage."""
    print("\n🧪 Checking test coverage...")
    
    checks = {}
    
    # Expected test files
    expected_tests = [
        "tests/test_api_admin.py",
        "tests/test_api_auth.py", 
        "tests/test_api_launches.py",
        "tests/test_database.py",
        "tests/test_models.py",
        "tests/test_repositories.py",
        "tests/test_scraping_utilities.py",
        "tests/test_spacex_scraper.py",
        "tests/test_nasa_scraper.py",
        "tests/test_wikipedia_scraper.py",
        "tests/test_data_validator.py",
        "tests/test_deduplicator.py",
        "tests/test_source_reconciler.py",
        "tests/test_task_scheduling.py",
        "tests/test_end_to_end.py",
        "tests/test_performance.py",
        "tests/test_system_integration.py",
        "tests/test_system_validation.py"
    ]
    
    existing_tests = [test for test in expected_tests if os.path.exists(test)]
    missing_tests = [test for test in expected_tests if not os.path.exists(test)]
    
    checks["test_files_exist"] = len(missing_tests) == 0
    
    if missing_tests:
        print(f"  ✗ Missing test files: {len(missing_tests)}")
        for test in missing_tests[:5]:  # Show first 5
            print(f"    - {test}")
        if len(missing_tests) > 5:
            print(f"    ... and {len(missing_tests) - 5} more")
    else:
        print("  ✓ All expected test files exist")
    
    print(f"  📊 Test coverage: {len(existing_tests)}/{len(expected_tests)} test files ({len(existing_tests)/len(expected_tests):.1%})")
    
    return checks


def check_documentation() -> dict:
    """Check documentation completeness."""
    print("\n📚 Checking documentation...")
    
    checks = {}
    
    # Required documentation files
    required_docs = [
        ("README.deployment.md", "Deployment guide"),
        ("docs/operational_procedures.md", "Operational procedures"),
        ("docs/deployment.md", "Detailed deployment docs"),
        ("docs/logging_and_monitoring.md", "Logging and monitoring"),
        ("docs/task_scheduling.md", "Task scheduling"),
    ]
    
    missing_docs = []
    for doc_file, description in required_docs:
        if os.path.exists(doc_file):
            print(f"  ✓ {description}: {doc_file}")
        else:
            print(f"  ✗ {description}: {doc_file}")
            missing_docs.append(doc_file)
    
    checks["documentation_complete"] = len(missing_docs) == 0
    
    # Check if documentation files have content
    content_checks = []
    for doc_file, description in required_docs:
        if os.path.exists(doc_file):
            try:
                with open(doc_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if len(content) > 100:  # Minimum content length
                    content_checks.append(True)
                else:
                    content_checks.append(False)
                    print(f"  ⚠ {doc_file} appears to be empty or too short")
            except Exception as e:
                content_checks.append(False)
                print(f"  ⚠ Could not read {doc_file}: {e}")
    
    checks["documentation_has_content"] = all(content_checks) if content_checks else False
    
    passed = sum(1 for result in checks.values() if result)
    total = len(checks)
    print(f"\n📊 Documentation: {passed}/{total} checks passed ({passed/total:.1%})")
    
    return checks


def generate_validation_report(all_checks: dict) -> str:
    """Generate a comprehensive validation report."""
    report = []
    report.append("=" * 80)
    report.append("SPACEX LAUNCH TRACKER - SYSTEM VALIDATION REPORT")
    report.append("=" * 80)
    report.append(f"Generated: {datetime.now().isoformat()}")
    report.append("")
    
    # Calculate overall statistics
    total_checks = sum(len(checks) for checks in all_checks.values())
    passed_checks = sum(sum(1 for result in checks.values() if result) for checks in all_checks.values())
    
    report.append("VALIDATION SUMMARY")
    report.append("-" * 40)
    report.append(f"Total Checks: {total_checks}")
    report.append(f"Passed: {passed_checks}")
    report.append(f"Failed: {total_checks - passed_checks}")
    report.append(f"Success Rate: {passed_checks/total_checks:.1%}")
    report.append("")
    
    # Detailed results by category
    for category, checks in all_checks.items():
        category_passed = sum(1 for result in checks.values() if result)
        category_total = len(checks)
        category_rate = category_passed / category_total if category_total > 0 else 0
        
        report.append(f"{category.upper().replace('_', ' ')}")
        report.append("-" * 40)
        report.append(f"Passed: {category_passed}/{category_total} ({category_rate:.1%})")
        
        # Show failed checks
        failed_checks = [name for name, result in checks.items() if not result]
        if failed_checks:
            report.append("Failed checks:")
            for check in failed_checks:
                report.append(f"  - {check.replace('_', ' ')}")
        report.append("")
    
    # Overall assessment
    report.append("OVERALL ASSESSMENT")
    report.append("-" * 40)
    
    success_rate = passed_checks / total_checks
    if success_rate >= 0.9:
        report.append("🎉 EXCELLENT - System is well-structured and ready for deployment")
    elif success_rate >= 0.8:
        report.append("✅ GOOD - System is mostly ready with minor issues to address")
    elif success_rate >= 0.7:
        report.append("⚠️ FAIR - System has some issues that should be addressed")
    else:
        report.append("❌ POOR - System has significant issues that must be fixed")
    
    report.append("")
    report.append("RECOMMENDATIONS")
    report.append("-" * 40)
    
    if success_rate < 1.0:
        report.append("1. Address all failed validation checks above")
        report.append("2. Ensure all required files and configurations are in place")
        report.append("3. Run comprehensive tests once issues are resolved")
        report.append("4. Review documentation for completeness")
    else:
        report.append("1. System validation passed - ready for testing")
        report.append("2. Run comprehensive integration tests")
        report.append("3. Perform deployment validation")
        report.append("4. Set up monitoring and alerting")
    
    report.append("")
    report.append("=" * 80)
    
    return "\n".join(report)


def main():
    """Main validation function."""
    print("🔍 SpaceX Launch Tracker - System Validation")
    print("=" * 60)
    
    # Run all validation checks
    all_checks = {
        "directory_structure": check_directory_structure(),
        "python_syntax": check_python_syntax(),
        "configuration_files": check_configuration_files(),
        "test_coverage": check_test_coverage(),
        "documentation": check_documentation()
    }
    
    # Generate report
    report = generate_validation_report(all_checks)
    print("\n" + report)
    
    # Save report
    os.makedirs("test_reports", exist_ok=True)
    report_file = f"test_reports/validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    try:
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n📄 Report saved to: {report_file}")
    except Exception as e:
        print(f"\n⚠️ Could not save report: {e}")
    
    # Exit with appropriate code
    total_checks = sum(len(checks) for checks in all_checks.values())
    passed_checks = sum(sum(1 for result in checks.values() if result) for checks in all_checks.values())
    success_rate = passed_checks / total_checks
    
    if success_rate >= 0.8:
        print("\n🎉 System validation completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ System validation failed. Please address the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()