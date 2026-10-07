
export interface BookInstance {
  id: string;
  book_id: string;
  barcode: string;
  call_number: string;
  status: 'available' | 'checked_out' | 'hold_shelf' | 'processing' | 'missing' | 'damaged';
  location: string;
  condition: string;
  condition_notes: string | null;
}

export interface Book {
  id: string;
  title: string;
  author: string;
  isbn: string;
  genres: string[];
  summary: string;
  publication_year: number;
  author_dates: string | null;
  stratum: number | null;
  publisher: string | null;
  page_count: number | null;
  setting_era: string | null;
  series: string | null;
  series_position: string | null;
  shelf_location: string | null;
  related_works: string[];
  notes: string | null;
  age_range: string | null;
  reading_level: string | null;
  illustrations: boolean;
  illustrator: string | null;
}

export interface BookWithAvailability extends Book {
  total_copies: number;
  available_copies: number;
}

export interface CatalogSearchResponse {
  total: number;
  books: BookWithAvailability[];
  limit: number;
  offset: number;
  message?: string;
}

export interface BookDetailResponse {
  book: Book;
  instances: BookInstance[];
  total_copies: number;
  available_copies: number;
}

export interface BookAvailability {
  book_id: string;
  total_copies: number;
  available: number;
  checked_out: number;
  on_hold_shelf: number;
  in_processing: number;
  earliest_return_date: string | null;
}

export interface BookAvailabilityResponse {
  availability: BookAvailability;
}
