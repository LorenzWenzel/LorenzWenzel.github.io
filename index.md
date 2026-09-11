---
layout: default
---

<section class="hero">
  <h1 class="hero-title">Lorenz Wenzel</h1>
  <p class="hero-lead">
    Notizen zum Bauen von KI Projekten in der Cloud. Hier fließen Erkenntnisse aus Arbeitsprojekten, privaten Projekten und Projekten aus selbstständiger Arbeit ein.
  </p>
</section>

{%- assign serie = site.categories['text2sql-agent-aws'] -%}
{%- assign serie_anzahl = serie | size -%}

<h2 class="section-heading">Serien</h2>

<ul class="card-list">
  <li>
    <a class="card" href="{{ '/text2sql-agent-aws/' | relative_url }}">
      <span class="card-kicker">Serie · {{ serie_anzahl }} Beiträge</span>
      <span class="card-title">text2SQL-Agent auf AWS</span>
      <span class="card-desc">Ein Agent, der natürlichsprachige Fragen in SQL übersetzt
      und gegen Amazon Athena ausführt — vom Rückgabeformat der Werkzeuge über die
      Herkunft des Domänenwissens bis zum Prompt Caching.</span>
    </a>
  </li>
</ul>

{%- assign andere = site.posts.size | minus: serie_anzahl -%}
{%- if andere > 0 %}
<h2 class="section-heading">Weitere Beiträge</h2>

<ul class="post-list-plain">
  {%- for post in site.posts -%}
  {%- unless post.categories contains 'text2sql-agent-aws' %}
  <li>
    <span class="post-date">{{ post.date | date: "%d.%m.%Y" }}</span>
    <a class="post-link" href="{{ post.url | relative_url }}">{{ post.title | escape }}</a>
  </li>
  {%- endunless -%}
  {%- endfor %}
</ul>
{%- endif %}
