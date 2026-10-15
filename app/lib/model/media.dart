/// Pictures and diagrams a tutor message carries (DOCS-contract §8).
library;

import 'package:tutor/model/json.dart';

/// A Wikimedia picture with attribution (§8).
class Img {
  /// Creates the record.
  const new({
    required this.url,
    required this.title,
    required this.author,
    required this.licence,
    required this.pageUrl,
    this.licenceUrl,
    this.term,
  });

  /// Parses an `IMG`.
  factory fromJson(Object? v) {
    final j = asJson(v, 'image');
    return Img(
      url: strOr(j, 'url') ?? '',
      title: str(j, 'title'),
      author: str(j, 'author'),
      licence: str(j, 'licence'),
      licenceUrl: strOr(j, 'licence_url'),
      pageUrl: str(j, 'page_url'),
      term: strOr(j, 'term'),
    );
  }

  /// Only Commons' upload and thumbnail hosts are ever loaded.
  static const allowedPrefixes = [
    'https://upload.wikimedia.org/',
    'https://thumb.wikimedia.org/',
  ];

  /// Thumbnail URL; empty when the worker could not resolve one (the
  /// attribution is still shown).
  final String url;

  /// Title.
  final String title;

  /// Author (plain text).
  final String author;

  /// Licence (plain text).
  final String licence;

  /// Licence link.
  final String? licenceUrl;

  /// Commons page (the attribution link).
  final String pageUrl;

  /// Search term that found it.
  final String? term;

  /// Whether [url] is on the image host allowlist.
  bool get loadable => allowedPrefixes.any(url.startsWith);

  /// Wire form.
  Json toJson() => compact({
    'url': url.isEmpty ? null : url,
    'title': title,
    'author': author,
    'licence': licence,
    'licence_url': licenceUrl,
    'page_url': pageUrl,
    'term': term,
  });
}

/// An inline worker-rendered SVG diagram (<= 8 KB).
class Dgm {
  /// Creates the record.
  const new({required this.title, required this.svg});

  /// Parses a `DGM`.
  factory fromJson(Object? v) {
    final j = asJson(v, 'diagram');
    return Dgm(title: str(j, 'title'), svg: str(j, 'svg'));
  }

  /// Title.
  final String title;

  /// SVG markup.
  final String svg;

  /// Wire form.
  Json toJson() => {'title': title, 'svg': svg};
}
