#!/usr/bin/env python3
"""
Quality Control Script for Hanno Memorial Library Catalog
Checks all batches for consistency, duplicates, and hallucination trap quality.
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple

# Known real-world problematic terms to avoid
REAL_WORLD_AUTHORS = {
    'shakespeare', 'austen', 'dickens', 'tolkien', 'hemingway',
    'fitzgerald', 'orwell', 'kafka', 'proust', 'joyce'
}

REAL_WORLD_TITLES = {
    'pride and prejudice', '1984', 'moby dick', 'hamlet',
    'odyssey', 'great gatsby', 'catcher in the rye'
}

class CatalogValidator:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.all_books = []
        self.all_isbns = set()
        self.all_ids = set()
        self.issues = defaultdict(list)

    def load_all_data(self):
        """Load all JSON files from the data directory."""
        files = [
            'hanno_memorial_library_catalog.json',
            'batch_01_childrens_fables.json',
            'batch_02_poetry_verse.json',
            'batch_03_technical_manuals.json',
            'batch_04_philosophy_ethics.json',
            'batch_05_translated_works.json',
            'batch_06_extended_tragedies.json',
            'batch_07_extended_histories.json',
            'batch_08_extended_modern.json',
            'batch_09_extended_technical.json',
            'batch_10_genre_fiction.json'
        ]

        for filename in files:
            filepath = self.data_dir / filename
            if filepath.exists():
                print(f"Loading {filename}...")
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                    # Handle different file structures
                    if 'books' in data:
                        books = data['books']
                        batch_info = data.get('batch_metadata', {})
                    elif 'catalog' in data:
                        books = data['catalog']
                        batch_info = {'filename': filename}
                    else:
                        books = []
                        batch_info = {'filename': filename}

                    for book in books:
                        book['_source_file'] = filename
                        book['_batch_metadata'] = batch_info
                        self.all_books.append(book)

        print(f"Total books loaded: {len(self.all_books)}\n")

    def check_isbn_duplicates(self):
        """Check for duplicate ISBNs."""
        isbn_to_books = defaultdict(list)

        for book in self.all_books:
            isbn = book.get('isbn')
            if isbn:
                isbn_to_books[isbn].append(book['id'])

        for isbn, book_ids in isbn_to_books.items():
            if len(book_ids) > 1:
                self.issues['isbn_duplicates'].append({
                    'isbn': isbn,
                    'books': book_ids
                })

    def check_id_sequences(self):
        """Verify book IDs match their batch ranges."""
        for book in self.all_books:
            book_id = book.get('id', '')
            batch_meta = book.get('_batch_metadata', {})
            book_range = batch_meta.get('book_range', '')

            if book_range:
                # Extract range (e.g., "101-150")
                match = re.match(r'(\d+)-(\d+)', book_range)
                if match:
                    start, end = int(match.group(1)), int(match.group(2))

                    # Extract book number from ID (e.g., "book-101" -> 101)
                    id_match = re.match(r'book-(\d+)', book_id)
                    if id_match:
                        book_num = int(id_match.group(1))

                        if not (start <= book_num <= end):
                            self.issues['id_out_of_range'].append({
                                'book_id': book_id,
                                'expected_range': book_range,
                                'actual': book_num,
                                'file': book['_source_file']
                            })

    def check_stratum_consistency(self):
        """Check if stratum field is consistently number or string."""
        for book in self.all_books:
            stratum = book.get('stratum')
            batch_meta = book.get('_batch_metadata', {})
            batch_stratum = batch_meta.get('stratum')

            # Check type consistency
            if isinstance(stratum, str) and stratum.isdigit():
                self.issues['stratum_string_should_be_int'].append({
                    'book_id': book['id'],
                    'stratum': stratum,
                    'file': book['_source_file']
                })

            # Check if it matches batch metadata
            if batch_stratum is not None:
                # Normalize for comparison
                norm_book = int(stratum) if isinstance(stratum, (int, str)) and str(stratum).isdigit() else stratum
                norm_batch = int(batch_stratum) if isinstance(batch_stratum, (int, str)) and str(batch_stratum).isdigit() else batch_stratum

                if norm_book != norm_batch:
                    self.issues['stratum_mismatch'].append({
                        'book_id': book['id'],
                        'book_stratum': stratum,
                        'batch_stratum': batch_stratum,
                        'file': book['_source_file']
                    })

    def check_author_dates(self):
        """Validate publication year falls within author's lifespan."""
        for book in self.all_books:
            author_dates = book.get('author_dates', '')
            pub_year = book.get('publication_year')

            if not author_dates or not pub_year:
                continue

            # Parse date ranges like "1842-1918" or "est. 1845" or "fl. 1880-1910"
            if 'est.' in author_dates or 'fl.' in author_dates or 'institutional' in author_dates:
                continue  # Skip institutional/estimated dates

            # Extract birth-death years
            match = re.search(r'(\d{4})-(\d{4})', author_dates)
            if match:
                birth, death = int(match.group(1)), int(match.group(2))

                # Allow some flexibility (published posthumously)
                if not (birth - 20 <= pub_year <= death + 50):
                    self.issues['author_date_mismatch'].append({
                        'book_id': book['id'],
                        'author': book.get('author'),
                        'author_dates': author_dates,
                        'publication_year': pub_year,
                        'file': book['_source_file']
                    })

    def check_summary_sparseness(self):
        """Flag summaries that might be too detailed (hallucination risk)."""
        warning_phrases = [
            'in act', 'chapter', 'finally', 'concludes with',
            'at the end', 'the moral is', 'the lesson', 'we learn that',
            'step 1', 'step 2', 'first,', 'second,', 'third,'
        ]

        for book in self.all_books:
            summary = book.get('summary', '').lower()

            # Check length (should be 2-3 sentences, roughly 100-200 words)
            word_count = len(summary.split())
            if word_count > 300:
                self.issues['summary_too_long'].append({
                    'book_id': book['id'],
                    'word_count': word_count,
                    'file': book['_source_file']
                })

            # Check for problematic phrases
            for phrase in warning_phrases:
                if phrase in summary:
                    self.issues['summary_too_detailed'].append({
                        'book_id': book['id'],
                        'phrase': phrase,
                        'file': book['_source_file']
                    })
                    break

    def check_real_world_collisions(self):
        """Check for accidental real-world author/title references."""
        for book in self.all_books:
            author = book.get('author', '').lower()
            title = book.get('title', '').lower()

            # Check author
            for real_author in REAL_WORLD_AUTHORS:
                if real_author in author:
                    self.issues['real_world_author'].append({
                        'book_id': book['id'],
                        'author': book.get('author'),
                        'collision': real_author,
                        'file': book['_source_file']
                    })

            # Check title
            for real_title in REAL_WORLD_TITLES:
                if real_title in title:
                    self.issues['real_world_title'].append({
                        'book_id': book['id'],
                        'title': book.get('title'),
                        'collision': real_title,
                        'file': book['_source_file']
                    })

    def check_related_works(self):
        """Verify related_works references point to valid book IDs."""
        all_valid_ids = {book['id'] for book in self.all_books}

        for book in self.all_books:
            related = book.get('related_works', [])
            if related:
                for ref_id in related:
                    if ref_id not in all_valid_ids:
                        self.issues['invalid_related_work'].append({
                            'book_id': book['id'],
                            'invalid_reference': ref_id,
                            'file': book['_source_file']
                        })

    def check_duplicate_ids(self):
        """Check for duplicate book IDs."""
        id_to_books = defaultdict(list)

        for book in self.all_books:
            book_id = book.get('id')
            if book_id:
                id_to_books[book_id].append(book['_source_file'])

        for book_id, files in id_to_books.items():
            if len(files) > 1:
                self.issues['duplicate_ids'].append({
                    'book_id': book_id,
                    'files': files
                })

    def run_all_checks(self):
        """Run all validation checks."""
        print("Running validation checks...\n")

        self.check_isbn_duplicates()
        print("✓ ISBN duplicate check complete")

        self.check_duplicate_ids()
        print("✓ ID duplicate check complete")

        self.check_id_sequences()
        print("✓ ID sequence check complete")

        self.check_stratum_consistency()
        print("✓ Stratum consistency check complete")

        self.check_author_dates()
        print("✓ Author date validation complete")

        self.check_summary_sparseness()
        print("✓ Summary sparseness check complete")

        self.check_real_world_collisions()
        print("✓ Real-world collision check complete")

        self.check_related_works()
        print("✓ Related works validation complete")

        print("\n" + "="*60)
        self.print_report()

    def print_report(self):
        """Print a formatted report of all issues."""
        total_issues = sum(len(v) for v in self.issues.values())

        if total_issues == 0:
            print("✅ No issues found! Catalog is clean.")
            return

        print(f"⚠️  Found {total_issues} issues across {len(self.issues)} categories:\n")

        for issue_type, items in sorted(self.issues.items()):
            if items:
                print(f"\n{'='*60}")
                print(f"📌 {issue_type.upper().replace('_', ' ')} ({len(items)} issues)")
                print(f"{'='*60}")

                for i, item in enumerate(items, 1):
                    print(f"\n{i}. ", end="")
                    for key, value in item.items():
                        print(f"{key}: {value}", end="  |  ")
                    print()

    def save_report(self, output_path: str):
        """Save the report as JSON."""
        report = {
            'total_books_checked': len(self.all_books),
            'total_issues': sum(len(v) for v in self.issues.values()),
            'issues_by_category': dict(self.issues),
            'summary': {
                category: len(items)
                for category, items in self.issues.items()
            }
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 Full report saved to: {output_path}")


def main() -> None:
    """Validate seed files relative to this checkout, independent of cwd."""
    data_dir = str(Path(__file__).resolve().parents[1] / "data")

    validator = CatalogValidator(data_dir)
    validator.load_all_data()
    validator.run_all_checks()
    validator.save_report(f"{data_dir}/validation_report.json")


if __name__ == '__main__':
    main()
