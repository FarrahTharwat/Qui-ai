# model/rag_summarizer.py
"""Enhanced RAG-based document summarization model"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib
from dataclasses import dataclass, asdict
from pathlib import Path

# RAG dependencies
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import pipeline as hf_pipeline, AutoTokenizer, AutoModel
import torch


@dataclass
class SummarizedPage:
    page_number: int
    original_text: str
    summary: str
    key_points: List[str]
    relevance_score: float
    semantic_similarity: float
    content_overlap: float
    context_boost: float


@dataclass
class SummarizedDocument:
    session_id: str
    original_cleaned_text: str
    combined_summary: str
    summarized_pages: List[SummarizedPage]
    pdf_path: str
    timestamp: str
    metadata: Dict[str, Any]
    image_analysis: Optional[Dict[str, Any]]
    summarization_metadata: Dict[str, Any]


class EnhancedRAGSummarizer:
    def __init__(self,
                 embedding_model_name: str = "all-MiniLM-L6-v2",
                 summarization_model: str = "facebook/bart-large-cnn",
                 chunk_size: int = 512,
                 overlap_size: int = 100,
                 relevance_threshold: float = 0.3):
        """
        Initialize enhanced RAG-based summarizer with improved relevance scoring
        """
        # Initialize model
        self.embedding_model = SentenceTransformer(embedding_model_name)
        self.summarizer = hf_pipeline("summarization", model=summarization_model)
        self.tokenizer = AutoTokenizer.from_pretrained(summarization_model)

        # Configuration
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.relevance_threshold = relevance_threshold

        # Storage for embeddings and chunks
        self.document_chunks = []
        self.chunk_embeddings = None
        self.page_embeddings = None
        self.global_keywords = set()

    def extract_keywords(self, text: str) -> set:
        """Extract important keywords from text"""
        words = text.lower().split()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is',
                      'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                      'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those'}
        keywords = {word for word in words if len(word) > 3 and word not in stop_words and word.isalpha()}
        return keywords

    def chunk_text_enhanced(self, text: str, page_idx: int) -> List[Dict]:
        """Enhanced text chunking with better metadata"""
        words = text.split()
        chunks = []
        page_keywords = self.extract_keywords(text)

        for i in range(0, len(words), self.chunk_size - self.overlap_size):
            chunk_text = " ".join(words[i:i + self.chunk_size])
            if chunk_text.strip():
                chunk_keywords = self.extract_keywords(chunk_text)
                chunks.append({
                    'text': chunk_text,
                    'page_idx': page_idx,
                    'chunk_idx': len(chunks),
                    'page_text': text,
                    'keywords': chunk_keywords,
                    'keyword_density': len(chunk_keywords) / max(len(chunk_text.split()), 1),
                    'position_weight': 1.0 - (i / max(len(words), 1)) * 0.3,
                    'length_score': min(1.0, len(chunk_text.split()) / 100)
                })

        return chunks

    def build_knowledge_base(self, pages: List[str]):
        """Build enhanced RAG knowledge base with better indexing"""
        self.document_chunks = []
        all_page_keywords = []

        # Create enhanced chunks from all pages
        for page_idx, page_text in enumerate(pages):
            page_chunks = self.chunk_text_enhanced(page_text, page_idx)
            self.document_chunks.extend(page_chunks)

            # Collect page-level keywords
            page_keywords = self.extract_keywords(page_text)
            all_page_keywords.append(page_keywords)

        # Build global keyword set for context scoring
        self.global_keywords = set()
        for keywords in all_page_keywords:
            self.global_keywords.update(keywords)

        # Generate embeddings for chunks
        chunk_texts = [chunk['text'] for chunk in self.document_chunks]
        self.chunk_embeddings = self.embedding_model.encode(chunk_texts)

        # Generate page-level embeddings
        self.page_embeddings = self.embedding_model.encode(pages)

        print(
            f"Built enhanced knowledge base with {len(self.document_chunks)} chunks and {len(self.global_keywords)} global keywords")

    def calculate_enhanced_relevance(self, query: str, chunks: List[Dict]) -> List[Dict]:
        """Calculate enhanced relevance scores using multiple factors"""
        query_keywords = self.extract_keywords(query)
        query_embedding = self.embedding_model.encode([query])

        enhanced_chunks = []

        for i, chunk in enumerate(chunks):
            # 1. Semantic similarity (cosine similarity)
            semantic_sim = float(cosine_similarity(query_embedding, [self.chunk_embeddings[i]])[0][0])

            # 2. Keyword overlap score
            chunk_keywords = chunk.get('keywords', set())
            keyword_overlap = len(query_keywords.intersection(chunk_keywords)) / max(
                len(query_keywords.union(chunk_keywords)), 1)

            # 3. Content density score
            content_density = chunk.get('keyword_density', 0) * chunk.get('length_score', 0)

            # 4. Position weight
            position_weight = chunk.get('position_weight', 1.0)

            # 5. Global keyword relevance
            global_relevance = len(chunk_keywords.intersection(self.global_keywords)) / max(len(self.global_keywords),
                                                                                            1)

            # 6. Length bonus for substantial chunks
            length_bonus = min(0.2, len(chunk['text'].split()) / 500)

            # Combine scores with weights
            enhanced_relevance = (
                    semantic_sim * 0.4 +
                    keyword_overlap * 0.25 +
                    content_density * 0.15 +
                    position_weight * 0.1 +
                    global_relevance * 0.05 +
                    length_bonus * 0.05
            )

            # Apply boost for high-quality chunks
            if semantic_sim > 0.7 or keyword_overlap > 0.3:
                enhanced_relevance *= 1.2

            # Apply contextual boost
            context_boost = min(0.3, global_relevance * 2)

            enhanced_chunk = chunk.copy()
            enhanced_chunk.update({
                'relevance_score': float(enhanced_relevance),
                'semantic_similarity': float(semantic_sim),
                'keyword_overlap': float(keyword_overlap),
                'content_density': float(content_density),
                'global_relevance': float(global_relevance),
                'context_boost': float(context_boost),
                'final_score': float(enhanced_relevance + context_boost)
            })

            enhanced_chunks.append(enhanced_chunk)

        return enhanced_chunks

    def retrieve_relevant_context(self, query: str, top_k: int = 5, min_relevance: float = None) -> List[Dict]:
        """Retrieve most relevant chunks with enhanced scoring"""
        if self.chunk_embeddings is None or len(self.document_chunks) == 0:
            return []

        # Use adaptive minimum relevance
        if min_relevance is None:
            min_relevance = self.relevance_threshold

        # Calculate enhanced relevance for all chunks
        enhanced_chunks = self.calculate_enhanced_relevance(query, self.document_chunks)

        # Filter by minimum relevance and sort by final score
        relevant_chunks = [
            chunk for chunk in enhanced_chunks
            if chunk['final_score'] >= min_relevance
        ]

        # Sort by final score
        relevant_chunks.sort(key=lambda x: x['final_score'], reverse=True)

        return relevant_chunks[:top_k]

    def cross_page_relevance_boost(self, page_idx: int, context_chunks: List[Dict]) -> List[Dict]:
        """Apply additional relevance boost for cross-page context"""
        if not context_chunks:
            return context_chunks

        boosted_chunks = []
        for chunk in context_chunks:
            boost_factor = 1.0

            # Boost chunks from different pages
            if chunk['page_idx'] != page_idx:
                boost_factor += 0.2

            # Extra boost for chunks with high semantic similarity
            if chunk.get('semantic_similarity', 0) > 0.6:
                boost_factor += 0.15

            # Boost for chunks with high keyword overlap
            if chunk.get('keyword_overlap', 0) > 0.3:
                boost_factor += 0.1

            boosted_chunk = chunk.copy()
            boosted_chunk['relevance_score'] = float(chunk['relevance_score'] * boost_factor)
            boosted_chunk['final_score'] = float(chunk['final_score'] * boost_factor)
            boosted_chunks.append(boosted_chunk)

        return boosted_chunks

    def summarize_with_context(self, text: str, context_chunks: List[Dict] = None) -> Dict[str, Any]:
        """Summarize text using enhanced RAG context"""
        # Validate input text
        if not text or len(text.strip()) < 10:
            print(f"Warning: Text too short for summarization: '{text[:50]}...'")
            return {
                'summary': text.strip() if text else "No content available",
                'key_points': [],
                'context_used': 0,
                'avg_relevance': 0.0
            }

        # Prepare enhanced context
        context_text = ""
        avg_relevance = 0.0

        if context_chunks:
            # Use top 2-3 chunks with highest relevance
            top_chunks = sorted(context_chunks, key=lambda x: x.get('final_score', 0), reverse=True)[:3]

            # Only use chunks with good relevance scores
            good_chunks = [chunk for chunk in top_chunks if chunk.get('final_score', 0) > 0.4]

            if good_chunks:
                # Combine context from multiple chunks
                context_parts = []
                total_relevance = 0

                for chunk in good_chunks:
                    chunk_text = chunk['text'][:300]
                    context_parts.append(chunk_text)
                    total_relevance += chunk.get('final_score', 0)

                context_text = " ".join(context_parts)
                avg_relevance = total_relevance / len(good_chunks)

        # Prepare full text with enhanced context integration
        if context_text and avg_relevance > 0.5:
            full_text = f"{text}\n\nRelevant context: {context_text}".strip()
        else:
            full_text = text.strip()

        words = full_text.split()
        if len(words) < 20:
            return {
                'summary': full_text,
                'key_points': self.extract_key_points(text),
                'context_used': len(context_chunks) if context_chunks else 0,
                'avg_relevance': float(avg_relevance)
            }

        # Enhanced text preparation for BART
        max_input_words = 900
        if len(words) > max_input_words:
            beginning = " ".join(words[:500])
            ending = " ".join(words[-300:])
            full_text = f"{beginning}... {ending}"

        # Generate summary with enhanced parameters
        try:
            input_length = len(full_text.split())
            max_summary_length = min(250, max(60, input_length // 3))
            min_summary_length = min(40, max_summary_length // 2)

            summary_result = self.summarizer(
                full_text,
                max_length=max_summary_length,
                min_length=min_summary_length,
                do_sample=False,
                truncation=True,
                clean_up_tokenization_spaces=True
            )
            summary = summary_result[0]['summary_text'].strip()

            # Enhanced summary validation
            if len(summary) < 15 or summary.lower().startswith('page') or len(summary.split()) < 5:
                raise ValueError("Low quality summary generated")

        except Exception as e:
            print(f"Summarization error: {e}")
            # Enhanced fallback strategy
            sentences = [s.strip() for s in text.split('.') if len(s.strip()) > 25]
            if sentences:
                scored_sentences = []
                for sent in sentences:
                    score = len(self.extract_keywords(sent)) * len(sent.split())
                    scored_sentences.append((sent, score))

                scored_sentences.sort(key=lambda x: x[1], reverse=True)
                top_sentences = [sent[0] for sent in scored_sentences[:3]]
                summary = '. '.join(top_sentences) + '.'
            else:
                summary = text[:300] + "..." if len(text) > 300 else text

        # Extract enhanced key points
        key_points = self.extract_key_points(text, max_points=6)

        return {
            'summary': summary,
            'key_points': key_points,
            'context_used': len(context_chunks) if context_chunks else 0,
            'avg_relevance': float(avg_relevance)
        }

    def extract_key_points(self, text: str, max_points: int = 6) -> List[str]:
        """Enhanced key point extraction with better scoring"""
        if not text or len(text.strip()) < 20:
            return []

        # Split into sentences with better cleaning
        sentences = []
        for sent in text.replace('\n', ' ').split('.'):
            sent = sent.strip()
            if (len(sent) > 20 and
                    not sent.lower().startswith('page') and
                    not sent.lower().startswith('figure') and
                    not sent.lower().startswith('table')):
                sentences.append(sent)

        if not sentences:
            return []

        # Enhanced sentence scoring
        scored_sentences = []
        text_keywords = self.extract_keywords(text)

        for sentence in sentences:
            score = 0
            words = sentence.split()
            sent_keywords = self.extract_keywords(sentence)

            # Length scoring
            word_count = len(words)
            if 10 <= word_count <= 30:
                score += 3
            elif 7 <= word_count <= 40:
                score += 2
            elif 5 <= word_count <= 50:
                score += 1

            # Keyword density bonus
            if sent_keywords:
                keyword_ratio = len(sent_keywords) / word_count
                score += keyword_ratio * 5

            # Important keywords bonus
            technical_terms = ['algorithm', 'method', 'approach', 'technique', 'optimization',
                               'process', 'strategy', 'implementation', 'performance', 'results',
                               'analysis', 'system', 'model', 'framework', 'evaluation', 'data',
                               'research', 'study', 'findings', 'conclusion', 'recommendation']

            tech_count = sum(1 for term in technical_terms if term.lower() in sentence.lower())
            score += tech_count * 1.5

            # Global keyword relevance
            global_overlap = len(sent_keywords.intersection(self.global_keywords))
            score += global_overlap * 0.8

            # Numerical data bonus
            if any(char.isdigit() for char in sentence):
                score += 1

            # Proper nouns bonus
            caps_count = sum(1 for word in words if word and word[0].isupper() and len(word) > 2)
            score += caps_count * 0.4

            # Sentence position bonus
            position = sentences.index(sentence)
            if position < 2 or position >= len(sentences) - 2:
                score += 0.5

            # Avoid generic phrases
            generic_phrases = ['in this', 'can be', 'will be', 'have been', 'as shown', 'it is', 'there are']
            if not any(phrase in sentence.lower() for phrase in generic_phrases):
                score += 1

            scored_sentences.append((sentence.strip(), score))

        # Sort by score and take top sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)

        # Filter out very low scores
        good_sentences = [(sent, score) for sent, score in scored_sentences if score > 2]

        key_points = [sent + '.' for sent, score in good_sentences[:max_points]]
        return key_points

    def reset_state(self):
        """Reset internal state for fresh processing"""
        self.document_chunks = []
        self.chunk_embeddings = None
        self.page_embeddings = None
        self.global_keywords = set()
        print("RAG state reset for fresh processing")

    def process_document(self, json_data: Dict[str, Any]) -> SummarizedDocument:
        """Process entire JSON document with enhanced RAG-based summarization"""

        # Reset state before each document processing
        self.reset_state()

        # Extract and validate polished pages
        polished_pages = json_data.get('polished_pages', [])
        if not polished_pages:
            raise ValueError("No polished_pages found in JSON data")

        print(f"Initial polished_pages count: {len(polished_pages)}")

        valid_pages = []
        for i, page in enumerate(polished_pages):
            print(f"Checking page {i + 1}: type={type(page)}, length={len(str(page)) if page else 0}")

            if (page is not None and
                    isinstance(page, str) and
                    len(page.strip()) > 10 and
                    not page.strip().lower().startswith('page_') and
                    not page.strip().lower().startswith('placeholder') and
                    page.strip() != '' and
                    not page.strip().isdigit()):

                valid_pages.append(page.strip())
                print(f"✓ Page {i + 1} accepted: {page[:100]}...")
            else:
                print(f"✗ Page {i + 1} rejected: '{str(page)[:100]}...'")

        print(f"Valid pages after filtering: {len(valid_pages)}")

        if not valid_pages:
            print("Warning: No valid page content found. Using cleaned_text as fallback.")
            cleaned_text = json_data.get('cleaned_text', '')
            if cleaned_text and len(cleaned_text) > 100:
                words = cleaned_text.split()
                chunk_size = max(300, len(words) // 4)
                valid_pages = []
                for i in range(0, len(words), chunk_size):
                    chunk = ' '.join(words[i:i + chunk_size])
                    if len(chunk.strip()) > 50:
                        valid_pages.append(chunk)
                print(f"Fallback pages created: {len(valid_pages)}")

            if not valid_pages:
                raise ValueError("No valid content found in polished_pages or cleaned_text")

        polished_pages = valid_pages
        print(f"Final processing: {len(polished_pages)} valid pages")

        if len(polished_pages) == 0:
            raise ValueError("No pages to process after validation")

        # Build enhanced knowledge base
        print("Building enhanced RAG knowledge base...")
        try:
            self.build_knowledge_base(polished_pages)
            print(f"Knowledge base built successfully with {len(self.document_chunks)} chunks")
        except Exception as e:
            print(f"Error building knowledge base: {e}")
            raise

        # Process each page with enhanced context
        summarized_pages = []
        all_summaries = []

        print(f"Starting to process {len(polished_pages)} pages...")

        for i, page_text in enumerate(polished_pages):
            try:
                print(f"\n--- Processing page {i + 1}/{len(polished_pages)} ---")
                print(f"Page length: {len(page_text)} chars")
                print(f"Page preview: {page_text[:100]}...")

                if not page_text or len(page_text.strip()) < 10:
                    print(f"Warning: Page {i + 1} is too short, skipping")
                    continue

                # Get enhanced relevant context
                query_text = page_text[:400] if len(page_text) > 400 else page_text

                try:
                    relevant_chunks = self.retrieve_relevant_context(query_text, top_k=5, min_relevance=0.25)
                    print(f"Retrieved {len(relevant_chunks)} relevant chunks")
                except Exception as e:
                    print(f"Error retrieving context for page {i + 1}: {e}")
                    relevant_chunks = []

                # Filter out chunks from same page and apply cross-page boost
                filtered_chunks = [chunk for chunk in relevant_chunks if chunk['page_idx'] != i]
                boosted_chunks = self.cross_page_relevance_boost(i, filtered_chunks)
                print(f"Using {len(boosted_chunks)} boosted chunks for context")

                # Summarize page with enhanced context
                try:
                    summary_result = self.summarize_with_context(page_text, boosted_chunks[:3])
                    print(f"Summary generated: {len(summary_result['summary'])} chars")
                except Exception as e:
                    print(f"Error summarizing page {i + 1}: {e}")
                    summary_result = {
                        'summary': page_text[:200] + "..." if len(page_text) > 200 else page_text,
                        'key_points': [],
                        'context_used': 0,
                        'avg_relevance': 0.0
                    }

                # Calculate enhanced relevance scores
                relevance_score = summary_result.get('avg_relevance', 0.0)
                semantic_similarity = np.mean(
                    [chunk.get('semantic_similarity', 0) for chunk in boosted_chunks[:3]]) if boosted_chunks else 0.0
                content_overlap = np.mean(
                    [chunk.get('keyword_overlap', 0) for chunk in boosted_chunks[:3]]) if boosted_chunks else 0.0
                context_boost = np.mean(
                    [chunk.get('context_boost', 0) for chunk in boosted_chunks[:3]]) if boosted_chunks else 0.0

                summarized_page = SummarizedPage(
                    page_number=i + 1,
                    original_text=page_text,
                    summary=summary_result['summary'],
                    key_points=summary_result['key_points'],
                    relevance_score=float(relevance_score),
                    semantic_similarity=float(semantic_similarity),
                    content_overlap=float(content_overlap),
                    context_boost=float(context_boost)
                )

                summarized_pages.append(summarized_page)
                all_summaries.append(summary_result['summary'])

                print(
                    f"✓ Page {i + 1} completed - Relevance: {relevance_score:.3f}, Semantic: {semantic_similarity:.3f}")

            except Exception as e:
                print(f"ERROR processing page {i + 1}: {e}")
                print(f"Page content preview: {str(page_text)[:200]}...")
                continue

        print(f"\nCompleted processing {len(summarized_pages)} pages successfully")

        if len(summarized_pages) == 0:
            raise ValueError("No pages were successfully processed")

        # Create enhanced combined summary
        print("Creating enhanced combined summary...")
        combined_text = ' '.join(all_summaries)
        if len(combined_text) > 100:
            doc_context = self.retrieve_relevant_context(combined_text[:500], top_k=3, min_relevance=0.4)
            final_summary_result = self.summarize_with_context(combined_text, doc_context)
            combined_summary = final_summary_result['summary']
        else:
            combined_summary = f"Document contains {len(polished_pages)} sections covering: " + '; '.join(
                all_summaries[:3])

        # Create final document with enhanced metadata
        summarized_doc = SummarizedDocument(
            session_id=json_data.get('session_id', ''),
            original_cleaned_text=json_data.get('cleaned_text', ''),
            combined_summary=combined_summary,
            summarized_pages=summarized_pages,
            pdf_path=json_data.get('pdf_path', ''),
            timestamp=datetime.now().isoformat(),
            metadata=json_data.get('metadata', {}),
            image_analysis=json_data.get('image_analysis'),
            summarization_metadata={
                'model_used': 'Enhanced RAG-based summarization with multi-factor relevance scoring',
                'embedding_model_dimension': 384,
                'total_pages': len(polished_pages),
                'total_chunks': len(self.document_chunks),
                'global_keywords_count': len(self.global_keywords),
                'avg_relevance_score': float(np.mean([page.relevance_score for page in summarized_pages])),
                'avg_semantic_similarity': float(np.mean([page.semantic_similarity for page in summarized_pages])),
                'avg_context_boost': float(np.mean([page.context_boost for page in summarized_pages])),
                'processing_timestamp': datetime.now().isoformat(),
                'content_validation': 'passed',
                'enhancement_version': '2.0'
            }
        )

        return summarized_doc