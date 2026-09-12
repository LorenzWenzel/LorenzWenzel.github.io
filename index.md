---
layout: default
---

<section class="hero">
  <h1 class="hero-title">Lorenz Wenzel</h1>
  <p class="hero-lead">{% include t.html key="hero_lead" %}</p>
</section>

<h2 class="section-heading">{% include t.html key="serien" %}</h2>

<ul class="card-list">
  {%- for s in site.data.serien %}
  {%- assign anzahl = site.categories[s.kategorie] | size %}
  <li>
    <a class="card" href="{{ s.url | relative_url }}">
      <span class="card-kicker">{% include t.html key="serie_kicker" %} · {% if anzahl == 0 %}{% include t.html key="in_arbeit_kurz" %}{% elsif anzahl == 1 %}{% include t.html key="ein_beitrag" %}{% else %}{{ anzahl }} {% include t.html key="beitraege_suffix" %}{% endif %}</span>
      <span class="card-title"><span data-lang-block="de">{{ s.titel }}</span><span data-lang-block="en">{{ s.titel_en | default: s.titel }}</span></span>
      <span class="card-desc"><span data-lang-block="de">{{ s.beschreibung }}</span><span data-lang-block="en">{{ s.beschreibung_en | default: s.beschreibung }}</span></span>
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
<h2 class="section-heading">{% include t.html key="weitere_beitraege" %}</h2>

<ul class="post-list-plain">
  {%- for post in site.posts -%}
  {%- assign in_serie = false -%}
  {%- for s in site.data.serien -%}
    {%- if post.categories contains s.kategorie -%}{%- assign in_serie = true -%}{%- endif -%}
  {%- endfor -%}
  {%- unless in_serie %}
  <li>
    <span class="post-date"><span data-lang-block="de">{{ post.date | date: "%d.%m.%Y" }}</span><span data-lang-block="en">{{ post.date | date: "%b %-d, %Y" }}</span></span>
    <a class="post-link" href="{{ post.url | relative_url }}"><span data-lang-block="de">{{ post.title | escape }}</span><span data-lang-block="en">{{ post.title_en | default: post.title | escape }}</span></a>
  </li>
  {%- endunless -%}
  {%- endfor %}
</ul>
{%- endif %}
