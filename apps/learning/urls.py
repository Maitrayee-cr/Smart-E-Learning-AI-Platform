from django.urls import path

from . import views

app_name = 'learning'

urlpatterns = [
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('my-learning/', views.my_learning, name='my_learning'),
    path('wishlist/', views.wishlist_page, name='wishlist_page'),
    path('cart/', views.cart_page, name='cart_page'),
    path('cart/add/<slug:slug>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/checkout/', views.checkout_cart, name='checkout_cart'),
    path('enroll/<slug:slug>/', views.enroll_course, name='enroll_course'),
    path('course/<slug:slug>/', views.enrolled_course_detail, name='enrolled_course_detail'),
    path('course/<slug:slug>/video-complete/', views.mark_course_video_complete, name='mark_course_video_complete'),
    path('course/<slug:slug>/engagement-analysis/', views.engagement_analysis, name='engagement_analysis'),
    path('engagement-snapshot/<int:snapshot_id>/delete/', views.delete_engagement_snapshot, name='delete_engagement_snapshot'),
    path('course/<slug:slug>/plagiarism-check/', views.plagiarism_check, name='plagiarism_check'),
    path('quiz/<int:quiz_id>/attempt/', views.attempt_quiz, name='attempt_quiz'),
    path('quiz/result/<int:result_id>/', views.quiz_result, name='quiz_result'),
    path('lesson/<int:lesson_id>/complete/', views.mark_lesson_complete, name='mark_lesson_complete'),
    path('course/<slug:slug>/review/', views.submit_review, name='submit_review'),
    path('certificates/', views.certificates_list, name='certificates_list'),
    path('payments/history/', views.payment_history, name='payment_history'),
    path('certificate/<int:enrollment_id>/', views.certificate_page, name='certificate_page'),
    path('wishlist/<slug:slug>/toggle/', views.wishlist_toggle, name='wishlist_toggle'),
    path('resource/<int:resource_id>/download/', views.download_resource, name='download_resource'),
]
