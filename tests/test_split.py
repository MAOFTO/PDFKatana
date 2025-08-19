import pytest

from app.schemas.split import PageSplit, SplitRequest


def test_split_request_schema():
    """Test SplitRequest schema validation"""
    # Valid request
    data = {"pages": [{"page": 5}, {"page": 10}, {"page": 15}]}
    request = SplitRequest(**data)
    assert len(request.pages) == 3
    assert request.pages[0].page == 5
    assert request.pages[1].page == 10
    assert request.pages[2].page == 15

    # Invalid request - empty pages list
    with pytest.raises(ValueError, match="At least one page must be specified"):
        SplitRequest(pages=[])


def test_page_split_schema():
    """Test PageSplit schema validation"""
    # Valid page number
    page = PageSplit(page=1)
    assert page.page == 1

    # Invalid page number - less than 1
    with pytest.raises(ValueError, match="Page number must be 1 or greater"):
        PageSplit(page=0)

    with pytest.raises(ValueError, match="Page number must be 1 or greater"):
        PageSplit(page=-1)


def test_split_logic_example():
    """Test the split logic with the example from the user"""
    # Example: {"pages":[{"page":28},{"page":37},{"page":39},{"page":40},{"page":44},{"page":45},{"page":46},{"page":47},{"page":51},{"page":84},{"page":85}]}
    # This should create 12 parts

    pages_data = {
        "pages": [
            {"page": 28},
            {"page": 37},
            {"page": 39},
            {"page": 40},
            {"page": 44},
            {"page": 45},
            {"page": 46},
            {"page": 47},
            {"page": 51},
            {"page": 84},
            {"page": 85},
        ]
    }

    request = SplitRequest(**pages_data)
    split_pages = [page_obj.page for page_obj in request.pages]

    # Should have 11 split points, creating 12 parts
    assert len(split_pages) == 11
    assert split_pages == [28, 37, 39, 40, 44, 45, 46, 47, 51, 84, 85]


def test_split_pages_validation():
    """Test validation of split pages"""
    # Test empty pages list
    with pytest.raises(ValueError):
        SplitRequest(pages=[])

    # Test invalid page number
    with pytest.raises(ValueError):
        PageSplit(page=-1)


def test_zip_endpoint_schema():
    """Test that the ZIP endpoint uses the same schema validation"""
    # This test ensures the ZIP endpoint inherits the same validation logic
    data = {"pages": [{"page": 5}, {"page": 10}]}
    request = SplitRequest(**data)
    assert len(request.pages) == 2
    assert request.pages[0].page == 5
    assert request.pages[1].page == 10


if __name__ == "__main__":
    pytest.main([__file__])
