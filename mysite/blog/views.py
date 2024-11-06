from django.shortcuts import render,get_object_or_404
from .models import Post, Comment
from django.views.generic import ListView
from django.core.paginator import Paginator,EmptyPage, PageNotAnInteger
from django.http import Http404,HttpResponseNotFound
from .forms import EmailPostForm, CommentForm, SearchForm
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.http import require_POST
from taggit.models import Tag
from django.db.models import Count
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity, TrigramWordSimilarity


# Create your views here.


# class PostListView(ListView):
#     queryset = Post.published.all()
#     context_object_name = 'posts'
#     paginate_by = 3
#     template_name = 'blog/list.html'

def post_list(request,tag_slug=None):
    post_list=Post.published.all()
    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        post_list = post_list.filter(tags__in=[tag])
        # post_list = post_list.filter(tags__slug=tag_slug)
    paginator=Paginator(post_list,4)
    page_number=request.GET.get('page', 1)
    # можно использовать либо get_page который обрабатывает ошибку неправильно заданной страницы и возращает последнюю если страница выходит
    posts = paginator.get_page(page_number)
    # либо использовать блок try except
    # try:
    #     posts = paginator.page(page_number)
    # except PageNotAnInteger:
    #     # Если page_number не целое число, то
    #     # выдать первую страницу
    #     posts = paginator.page(1)
    # except EmptyPage:
    #     # Если page_number находится вне диапазона, то
    #     # выдать последнюю страницу результатов
    #     posts = paginator.page(paginator.num_pages)
    return render(request,'blog/list.html',{'posts':posts, 'tag':tag})

# возращает весь список статей на одной странице
# def post_list(request):
#     posts = Post.published.all()
#     return render(request,
#                   'blog/list.html',
#                   {'posts': posts})

# используем url с датой и слагом

def post_share(request, post_id):
    post= get_object_or_404(Post,
                            id=post_id,
                            status=Post.Status.PUBLISHED
                            )
    sent=False
    if request.method == 'POST':
        form=EmailPostForm(request.POST)
        if form.is_valid():
            cd=form.cleaned_data
            post_url=request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cd['name']} recommends you read {post.title}"
            message = f"Read {post.title} at {post_url}\n\n" \
                      f"{cd['name']}\'s ({cd['email']}) comments: {cd['comments']}"
            send_mail(subject,message,settings.EMAIL_HOST_USER, [cd['to']])
            sent=True
    else:
        form=EmailPostForm()
    return render(request, 'blog/share.html', {'post':post,'form':form,'sent':sent})

def post_detail(request, year, month, day, post):
    post = get_object_or_404(Post,
                             status=Post.Status.PUBLISHED,
                             slug=post,
                             publish__year=year,
                             publish__month=month,
                             publish__day=day)
    # Список активных комментариев к этому посту
    comments = post.comments.filter(active=True)
    # Форма для комментирования пользователями
    form = CommentForm()
    # Список схожих постов
    post_tags_ids = post.tags.values_list('id', flat=True)
    print(post_tags_ids)
    similar_posts = Post.published.filter(tags__in=post_tags_ids) \
        .exclude(id=post.id)
    print(similar_posts)
    similar_posts = similar_posts.annotate(same_tags=Count('tags')) \
                        .order_by('-same_tags', '-publish')[:4]
    print(similar_posts)
    return render(request,
                  'blog/detail.html',
                  {'post': post,
                   'comments': comments,
                   'form': form,
                   'similar_posts':similar_posts})

# юрл по номеру id
# def post_detail(request, id):
#     try:
#         post=Post.published.get(id=id)
#     except Post.DoestNotExist:
#         return Http404 ('No Post found.')
#     return render(request, 'blog/post/detail.html', {'post':post})

@require_POST
def post_comment(request, post_id):
    post = get_object_or_404(Post,
                             id=post_id,
                             status=Post.Status.PUBLISHED)
    comment = None
    # Комментарий был отправлен
    form = CommentForm(data=request.POST)
    if form.is_valid():
        # Создать объект класса Comment, не сохраняя его в базе данных
        comment = form.save(commit=False)
        # Назначить пост комментарию
        comment.post = post
        # Сохранить комментарий в базе данных
        comment.save()
    return render(request, 'blog/comment.html',
                  {'post': post,
                   'form': form,
                   'comment': comment})

def post_search(request):
    form = SearchForm()
    query = None
    results = []

    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            # ------------------------
            A = 1.0
            B = 0.4
            results = Post.published.annotate(
                similarity=(A / (A + B) * TrigramSimilarity('title', query)
                            + B / (A + B) * TrigramWordSimilarity(query, 'body'))
            ).filter(similarity__gte=0.1).order_by('-similarity')
            # -------------------------------
            # results = Post.published.annotate(
            #     similarity=TrigramSimilarity('title', query),
            # ).filter(similarity__gt=0.1).order_by('-similarity')
            # ------------------------------
            # search_vector = SearchVector('title', 'body', config='russian')
            # search_query = SearchQuery(query, config='russian')
            # results = Post.published.annotate(
            #     search=search_vector,
            #     rank=SearchRank(search_vector, search_query)
            # ).filter(search=search_query).order_by('-rank')

    return render(request,
                  'blog/search.html',
                  {'form': form,
                   'query': query,
                   'results': results})