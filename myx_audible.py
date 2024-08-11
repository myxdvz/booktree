import os, sys, subprocess, shlex, re
from subprocess import call
from pprint import pprint
import json
import myx_utilities
import myx_classes
import myx_args

def getAudibleBook(client, asin="", title="", authors="", narrators="", keywords=""):
    if myx_args.params.verbose:
        print (f"getAudibleBook\n\tasin:{asin}\n\ttitle:{title}\n\tauthors:{authors}\n\tnarrators:{narrators}\n\tkeywords:{keywords}")
    
    enBooks=[]
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
                "response_groups": (
                    "series, product_attrs, relationships, contributors, product_desc, product_extended_attrs"
                )
            },
        )

        r.raise_for_status()
        books = r.json()
        #pprint(books)
    
        #check for ["product"] or ["products"]
        if "product" in books.keys():
            enBooks.append(books["product"])
        elif "products" in books.keys():
            for book in books["products"]:
                #ignore non-english books
                if (book["language"] == "english"):
                    enBooks.append(book)

        return enBooks
    except Exception as e:
        print(f"Error searching audible: {e}")

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

def getBookByAuthorTitle(client, author, title):
    print ("getBookByAuthorTitle: ", author, ", ", title)
    enBooks=[]
    try:
        r = client.get (
            f"https://api.audible.com/1.0/catalog/products",
            params={
                "author": myx_utilities.strip_accents(author),
                "title": title,
                "response_groups": (
                    "series, product_attrs, relationships, contributors, product_desc, product_extended_attrs"
                )
            },
        )

        r.raise_for_status()
        books = r.json()
        #pprint(books)

        for book in books["products"]:
            #ignore non-english books
            if (book["language"] == "english"):
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
        if 'runtime_length_min' in product: book.length=product["runtime_length_min"]
        if 'authors' in product: 
            for author in product["authors"]:
                book.authors.append(myx_classes.Contributor(str(author["name"])))
        if 'narrators' in product: 
            for narrator in product["narrators"]:
                book.narrators.append(myx_classes.Contributor(str(narrator["name"])))
        if 'publication_name' in product: book.publicationName=str(product["publication_name"])
        if 'relationships' in product: 
            for relationship in product["relationships"]:
                #if this relationship is a series
                if (str(relationship["relationship_type"]) == "series"):
                    book.series.append(myx_classes.Series(str(relationship["title"]), str(relationship["sequence"])))
        
        if myx_args.params.verbose:
            pprint (book)
            
        return book
    else:
        return None
