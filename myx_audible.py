import os, sys, subprocess, shlex, re
from subprocess import call
from pprint import pprint
import json
import myx_utilities
import myx_classes

def getAudibleBook(client, cfg, asin="", title="", authors="", narrators="", keywords="", language="english"):
    print (f"Searching Audible for\n\tasin:{asin}\n\ttitle:{title}\n\tauthors:{authors}\n\tnarrators:{narrators}\n\tkeywords:{keywords}")

    enBooks=[]
    cacheKey = myx_utilities.getHash(f"{asin}{title}{authors}{narrators}{keywords}")
    if myx_utilities.isCached(cacheKey, "audible", cfg):
        print (f"Retrieving {cacheKey} from audible")

        #this search has been done before, retrieve the results
        books = myx_utilities.loadFromCache(cacheKey, "audible")

    else:
        try:
            if len(asin) : 
                p=f"https://api.audible.com/1.0/catalog/products/{asin}"
            else:
                p=f"https://api.audible.com/1.0/catalog/products"

            r = client.get (
                p,
                params={
                    "asin": asin,
                    "title": title,
                    "author": authors,
                    "narrator": narrators,
                    "keywords": keywords,
                    "products_sort_by": "Relevance",
                    "response_groups": (
                        "series, product_attrs, relationships, contributors, product_desc, product_extended_attrs"
                    )
                },
            )

            r.raise_for_status()
            books = r.json()

            #cache this results
            myx_utilities.cacheMe(cacheKey, "audible", books, cfg)

        except Exception as e:
                print(f"Error searching audible: {e}")

    
    #check for ["product"] or ["products"]
    if "product" in books.keys():
        enBooks.append(books["product"])
    elif "products" in books.keys():
        for book in books["products"]:
            #ignore non-english books
            if ("language" in book) and (book["language"] == language):
                enBooks.append(book)

    return enBooks

def getBookByAsin(client, asin):
    print ("getBookByASIN: ", asin)
    try:
        r = client.get (
            f"https://api.audible.com/1.0/catalog/products/{asin}",
            params={
                "response_groups": (
                    "series, product_attrs, relationships, contributors, product_desc, product_extended_attrs"
                )
            },
        )
        
        r.raise_for_status()
        return r.json()["product"]
    
    except Exception as e:
        print(e)

def getBookByAuthorTitle(client, author, title, language="english"):
    print ("getBookByAuthorTitle: ", author, ", ", title)
    enBooks=[]
    try:
        r = client.get (
            f"https://api.audible.com/1.0/catalog/products",
            params={
                "author": myx_utilities.strip_accents(author),
                "title": title,
                "response_groups": (
                    "series, product_attrs, contributors, product_desc, product_extended_attrs"
                )
            },
        )

        r.raise_for_status()
        books = r.json()
        #pprint(books)

        for book in books["products"]:
            #ignore non-english books
            if (book["language"] == language):
                enBooks.append(book)

        print("Found ", len(enBooks), " books")
        return enBooks
    except Exception as e:
        print(e)

def product2Book(product):
    #product is an Audible product json
    if product is not None:
        book=myx_classes.Book()
        if 'asin' in product: book.asin=str(product["asin"])
        if 'title' in product: book.title=str(product["title"])
        if 'subtitle' in product: book.subtitle=str(product["subtitle"])
        if 'publisher_summary' in product: book.description=str(product["publisher_summary"])
        if 'runtime_length_min' in product: book.length=product["runtime_length_min"]
        if 'authors' in product: 
            for author in product["authors"]:
                book.authors.append(myx_classes.Contributor(str(author["name"])))
        if 'narrators' in product: 
            for narrator in product["narrators"]:
                book.narrators.append(myx_classes.Contributor(str(narrator["name"])))
        if 'publication_name' in product: book.publicationName=str(product["publication_name"])
        if 'series' in product: 
            for s in product["series"]:
                book.series.append(myx_classes.Series(str(s["title"]), str(s["sequence"])))
        if 'language' in product: book.language=str(product ["language"])

            
        return book
    else:
        return None
