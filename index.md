---
layout: default
---

<section class="hero">
  <h1 class="hero-title">Lorenz Wenzel</h1>
  <p class="hero-lead">
    Notizen zum Bauen von KI Projekten in der Cloud. Hier fließen Erkenntnisse aus Arbeitsprojekten, privaten Projekten und Projekten aus selbstständiger Arbeit ein.
  </p>
</section>

<h2 class="section-heading">Serien</h2>

<ul class="card-list">
  {%- for s in site.data.serien %}
  {%- assign anzahl = site.categories[s.kategorie] | size %}
  <li>
    <a class="card" href="{{ s.url | relative_url }}">
      <span class="card-kicker">Serie · {% if anzahl == 0 %}in Arbeit{% elsif anzahl == 1 %}1 Beitrag{% else %}{{ anzahl }} Beiträge{% endif %}</span>
      <span class="card-title">{{ s.titel }}</span>
      <span class="card-desc">{{ s.beschreibung }}</span>
    </a>
  </li>
  {%- endfor %}
</ul>

{%- comment -%}
Beiträge, die zu keiner Serie gehören. Der Abschnitt erscheint nur, wenn es welche gibt.
{%- endcomment -%}
{%- assign serien_posts = 0 -%}
{%- for s in site.data.serien -%}
  {%- assign n = site.categories[s.kategorie] | size -%}
  {%- assign serien_posts = serien_posts | plus: n -%}
{%- endfor -%}
{%- assign andere = site.posts.size | minus: serien_posts -%}
{%- if andere > 0 %}
<h2 class="section-heading">Weitere Beiträge</h2>

<ul class="post-list-plain">
  {%- for post in site.posts -%}
  {%- assign in_serie = false -%}
  {%- for s in site.data.serien -%}
    {%- if post.categories contains s.kategorie -%}{%- assign in_serie = true -%}{%- endif -%}
  {%- endfor -%}
  {%- unless in_serie %}
  <li>
    <span class="post-date">{{ post.date | date: "%d.%m.%Y" }}</span>
    <a class="post-link" href="{{ post.url | relative_url }}">{{ post.title | escape }}</a>
  </li>
  {%- endunless -%}
  {%- endfor %}
</ul>
{%- endif %}
