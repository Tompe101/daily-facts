---
layout: page
title: Categories
permalink: /categories/
---

Browse daily facts and updates by category:

{% for category in site.categories %}
  ## {{ category[0] }}
  <ul>
    {% for post in category[1] %}
      <li>
        <a href="{{ post.url | relative_url }}">{{ post.title }}</a> 
        <small>— {{ post.date | date: "%b %d, %Y" }}</small>
      </li>
    {% endfor %}
  </ul>
{% endfor %}
