def test_package_imports_and_has_version():
    import refereekit
    assert isinstance(refereekit.__version__, str)
    assert refereekit.__version__
