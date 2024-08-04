import audible
import os, sys, subprocess, shlex, re
from subprocess import call
from pprint import pprint
import json
import myx_utilities
import myx_classes
import myx_args

#MyAudible Functions
def audibleConnect(authMode, authFile, locale="us"):
    if myx_args.params.verbose:
        print (f"Authenticating via {authMode} : locale = {locale}, authfile = {authFile}...")

    match authMode:
        case "browser": 
            auth = audible.Authenticator.from_login_external(locale)
        case "file":
            auth = authenticateByFile(authFile)
        case _:
            auth = authenticateByLogin(authFile, myx_args.params.user, myx_args.params.pwd)
    client = audible.Client(auth)   

    return auth, client 

def audibleDisconnect(auth):
    # deregister device when done
    auth.deregister_device()

def authenticateByFile(authFilename):
    auth = audible.Authenticator.from_file(authFilename)
    return auth

def authenticateByLogin(authFilename, username, password):
    auth = audible.Authenticator.from_login(username, password, locale="us")

    # store credentials to file
    auth.to_file(filename=authFilename, encryption="json", password=password)

    # save again
    auth.to_file()

    # load credentials from file
    auth = audible.Authenticator.from_file(filename=authFilename, password=password)
    return auth

def getAudibleBook(client, asin="", title="", authors="", narrators="", keywords=""):
    if myx_args.params.verbose:
        print (f"getAudibleBook\n\tasin:{asin}\n\ttitle:{title}\n\tauthors:{authors}\n\tnarrators:{narrators}\n\tkeywords:{keywords}")
    
    enBooks=[]
    try:
        books = client.get (
            path=f"catalog/products",
            params={
                "asin": asin,
                "title": title,
                "author":authors,
                "narrator": narrators,
                "keywords": keywords,
                "response_groups": (
                    "sku, series, product_attrs, relationships, contributors,"
                    "product_extended_attrs, product_desc, product_plan_details"
                )
            },
        )
        for book in books["products"]:
            #ignore non-english books
            if (book["language"] == "english"):
                enBooks.append(book)

        return enBooks
    except Exception as e:
        print(e)

def getBookByAsin(client, asin):
    print ("getBookByASIN: ", asin)
    try:
        book = client.get (
            path=f"catalog/products/{asin}",
            params={
                "response_groups": (
                    "sku, series, product_attrs, relationships, contributors,"
                    "product_extended_attrs, product_desc, product_plan_details"
                )
            },
        )
        return book["product"]
    except Exception as e:
        print(e)

def getBookByAuthorTitle(client, author, title):
    print ("getBookByAuthorTitle: ", author, ", ", title)
    enBooks=[]
    try:
        books = client.get (
            path=f"catalog/products",
            params={
                "author": myx_utilities.strip_accents(author),
                "title": title,
                "response_groups": (
                    "sku, series, product_attrs, relationships, contributors,"
                    "product_extended_attrs, product_desc, product_plan_details"
                )
            },
        )
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
        if 'asin' in product: book.asin=product["asin"]
        if 'title' in product: book.title=product["title"]
        if 'subtitle' in product: book.subtitle=product["subtitle"]
        if 'runtime_length_min' in product: book.length=product["runtime_length_min"]
        if 'authors' in product: 
            for author in product["authors"]:
                book.authors.append(myx_classes.Contributor(author["name"]))
        if 'narrators' in product: 
            for narrator in product["narrators"]:
                book.narrators.append(myx_classes.Contributor(narrator["name"]))
        if 'publication_name' in product: book.publicationName=product["publication_name"]
        if 'relationships' in product: 
            for relationship in product["relationships"]:
                #if this relationship is a series
                if (relationship["relationship_type"] == "series"):
                    book.series.append(myx_classes.Series(relationship["title"], relationship["sequence"]))
        
        if myx_args.params.verbose:
            pprint (book)
            
        return book
    else:
        return None
