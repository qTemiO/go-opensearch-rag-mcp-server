async def form_filter_block(books: list[str]) -> list[dict]:
    terms = []

    for book_name in books:
        terms.append({
            "term": {
                "document_name.keyword": book_name
            }
        })

    return terms


async def form_filter(inclusive_books: list[str], exclusive_books: list[str]) -> dict:
    should = await form_filter_block(books=inclusive_books)
    must_not = await form_filter_block(books=exclusive_books)

    filter_ = {
        "bool": {
            "should": should,
            "must_not": must_not,
        }
    }

    return filter_
