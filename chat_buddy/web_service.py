import aiohttp
import asyncio
from bs4 import BeautifulSoup
import requests
from urllib.parse import quote
import time
from datetime import datetime, timedelta

# Simple in-memory cache to avoid duplicate requests
search_cache = {}
CACHE_DURATION = 3600  # Cache for 1 hour

def get_cached_search(query):
    """Get cached search results if they exist and are fresh"""
    if query in search_cache:
        cached_time, cached_results = search_cache[query]
        if datetime.now() - cached_time < timedelta(seconds=CACHE_DURATION):
            return cached_results
    return None

def cache_search_results(query, results):
    """Cache search results"""
    search_cache[query] = (datetime.now(), results)

def search_google_news(query, max_results=3):
    """
    Search for current news using Google News scraping
    Returns list of news articles with title, link, and snippet
    """
    try:
        # Check cache first
        cached = get_cached_search(f"news:{query}")
        if cached:
            return cached
        
        news_results = []
        
        # Use simple Google search approach
        search_url = f"https://news.google.com/search?q={quote(query)}"
        
        headers = {
            'User-Agent': 'LearnBuddy/1.0 (Educational AI Assistant; +https://example.com/about)'
        }
        
        try:
            response = requests.get(search_url, headers=headers, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract news articles (basic approach)
            articles = soup.find_all('article', limit=max_results)
            
            for article in articles:
                try:
                    title_elem = article.find(['h2', 'h3'])
                    link_elem = article.find('a')
                    
                    if title_elem and link_elem:
                        title = title_elem.get_text(strip=True)
                        link = link_elem.get('href', '')
                        
                        news_results.append({
                            'title': title,
                            'link': link,
                            'source': 'Google News'
                        })
                except Exception as e:
                    print(f"Error parsing article: {e}")
                    continue
            
            # Cache results
            cache_search_results(f"news:{query}", news_results)
            return news_results
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Google News: {e}")
            return []
            
    except Exception as e:
        print(f"Error in search_google_news: {e}")
        return []

def search_wikipedia(query):
    """
    Search Wikipedia for information about a topic
    Returns relevant Wikipedia summary
    """
    try:
        # Check cache first
        cached = get_cached_search(f"wiki:{query}")
        if cached:
            return cached
        
        # Use Wikipedia API with proper headers
        search_url = "https://en.wikipedia.org/w/api.php"
        
        headers = {
            'User-Agent': 'LearnBuddy/1.0 (Educational AI Assistant; +https://example.com/about)'
        }
        
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': query,
            'format': 'json',
            'srlimit': 3
        }
        
        response = requests.get(search_url, params=params, headers=headers, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        results = data.get('query', {}).get('search', [])
        
        if results:
            # Get first result
            first_result = results[0]
            title = first_result['title']
            snippet = first_result['snippet'].replace('<span class="searchmatch">', '').replace('</span>', '')
            
            result = {
                'title': title,
                'snippet': snippet,
                'url': f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            }
            
            # Cache results
            cache_search_results(f"wiki:{query}", result)
            return result
        
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"Error searching Wikipedia: {e}")
        return None
    except Exception as e:
        print(f"Error in search_wikipedia: {e}")
        return None

def search_web(query, max_results=3):
    """
    Perform web search for current information
    Uses multiple sources: News, Wikipedia, and general search
    Returns formatted search results
    """
    try:
        # Check cache first
        cached = get_cached_search(f"web:{query}")
        if cached:
            return cached
        
        results = {
            'query': query,
            'news': [],
            'knowledge': None,
            'timestamp': datetime.now().isoformat()
        }
        
        # Search news
        try:
            news_results = search_google_news(query, max_results)
            results['news'] = news_results[:max_results]
        except:
            pass
        
        # Search Wikipedia for general knowledge
        try:
            wiki_result = search_wikipedia(query)
            if wiki_result:
                results['knowledge'] = wiki_result
        except:
            pass
        
        # Cache results
        cache_search_results(f"web:{query}", results)
        return results
        
    except Exception as e:
        print(f"Error in search_web: {e}")
        return {
            'query': query,
            'news': [],
            'knowledge': None,
            'error': str(e)
        }

def format_search_results_for_ai(search_results):
    """
    Format search results in a way that's useful for the AI
    Returns a string that can be prepended to AI context
    """
    if not search_results:
        return ""
    
    formatted = "\n=== CURRENT INFORMATION (Web Search Results) ===\n"
    
    # Add news results
    if search_results.get('news'):
        formatted += "\nLatest News:\n"
        for i, article in enumerate(search_results['news'], 1):
            formatted += f"{i}. {article['title']}\n"
            if 'link' in article:
                formatted += f"   Source: {article['source']}\n"
    
    # Add Wikipedia knowledge
    if search_results.get('knowledge'):
        knowledge = search_results['knowledge']
        formatted += f"\nBackground Information:\n"
        formatted += f"Topic: {knowledge['title']}\n"
        formatted += f"Summary: {knowledge['snippet']}\n"
    
    formatted += "\n=== Use this current information to answer the user's question ===\n"
    
    return formatted

async def search_web_async(query):
    """
    Asynchronous version of web search (non-blocking)
    """
    # Run blocking search in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_web, query)

def is_current_event_question(user_message):
    """
    Detect if user is asking about current events/news
    Returns True if question likely needs real-time information
    """
    current_keywords = [
        'now', 'today', 'current', 'latest', 'recent', 'happening',
        'news', 'breaking', 'right now', 'this week', 'this month',
        'what is', 'what\'s', 'tell me about', 'update on',
        'situation', 'event', 'incident', 'crisis', 'disaster',
        'election', 'weather', 'stock', 'crypto', 'vaccine'
    ]
    
    message_lower = user_message.lower()
    
    # Check for time-sensitive keywords
    has_current_keyword = any(keyword in message_lower for keyword in current_keywords)
    
    # Check if question asks about specific recent timeframe
    has_time_reference = any(word in message_lower for word in ['2024', '2025', '2026', 'january', 'february', 'march'])
    
    return has_current_keyword or has_time_reference
