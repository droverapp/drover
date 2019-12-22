from django.shortcuts import render

def home(request):
    return render(request, 'home.html')

def mapview(request):
    if request.GET.get('lon', None) and request.GET.get('lat', None):
        return render(request, 'mapview.html', 
        {'lat': request.GET.get('lat', None), 'lon': request.GET.get('lon', None)})
    return render(request, 'home.html')
