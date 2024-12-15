#if not 'Images' in $StationInfo
#stop
#end if
#set $image_items = $StationInfo.Images.get('image_items', [])
#if $image_items
<div class="row $global_station_info_classes">
    <div id="imageCarousel" class="carousel slide p-3 " data-bs-ride="carousel">
    #if $StationInfo.Images.get('carouselIndicators','true').lower == 'true' 
    <div class="carousel-indicators">
        #set $imageCount = 0
        #for $image_item_key in $image_items
        #set $itemActive = $imageCount == 0 and 'active' or ''
        #set $image_item = $StationInfo.Images[$image_item_key]
        <button type="button" data-bs-target="#imageCarousel" data-bs-slide-to="$imageCount" 
          class="$itemActive" aria-current="true" aria-label="$image_item.imageCaptionHeading">
        </button>
        #set $imageCount += 1    
        #end for
    </div>
    #end if
    <div class="carousel-inner">
        #set $imageCount = 0
        #for $image_item_key in $image_items
        #set $itemActive = $imageCount == 0 and 'active' or ''
        #set $image_item = $StationInfo.Images[$image_item_key]
        <div class="carousel-item $itemActive">
            #set $imagePadding = $image_item.get('imagePadding', '0')
            #set $imageReload = $image_item.get('imageReload', '0')
            #if $image_item.get('useLightbox', 'true').lower == 'true'
            <img src="$image_item.imageUrl" class="d-block w-100" data-bs-toggle="modal" 
              data-bs-target="#imageCarousel-$imageCount-Modal" alt="$image_item.imageCaptionHeading" 
              style="cursor: pointer; padding-top: $imagePadding; padding-bottom: $imagePadding;" 
              onload='imageRefresh(this, $imageReload * 1000 * 60);'>
            #else
            <a href="$image_item.imageLink"><img src="$image_item.imageUrl" class="d-block w-100" 
              alt="$image_item.imageCaptionHeading" 
              style="padding-top: $imagePadding; padding-bottom: $imagePadding;" 
              onload='imageRefresh(this, $imageReload * 1000 * 60);'></a>
            #end if
            #if $StationInfo.Images.get('carouselCaptions', 'true').lower == 'true'
            <div class="carousel-caption d-none d-md-block rounded-3" style="cursor: pointer;">
                <h5>$image_item.imageCaptionHeading</h5>
                <p>$image_item.imageCaptionText</p>
            </div>
            #end if
        </div>
        #set $imageCount += 1
        #end for
    </div>
    #if $StationInfo.Images.get('carouselNextPrevButtons', 'true').lower == 'true'
    <button class="carousel-control-prev" type="button" data-bs-target="#imageCarousel" data-bs-slide="prev">
        <span class="carousel-control-prev-icon" aria-hidden="true"></span>
        <span class="visually-hidden">Previous</span>
    </button>
    <button class="carousel-control-next" type="button" data-bs-target="#imageCarousel" data-bs-slide="next">
        <span class="carousel-control-next-icon" aria-hidden="true"></span>
        <span class="visually-hidden">Next</span>
    </button>
    </div>
    #end if
</div>
#set $imageCount = 0
#for $image_item_key in $image_items
#set $image_item = $StationInfo.Images[$image_item_key]
#if $image_item.useLightbox == 'true'
<div class="modal fade" id="imageCarousel-$imageCount-Modal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-fullscreen-$image_item.get('lightboxFullScreen', 'lg-down') 
      modal-$image_item.get('lightboxSize', 'lg')">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">$image_item.imageCaptionHeading</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"
                        aria-label="Close"></button>
            </div>
            <div class="modal-body">
                #if $image_item.lightboxStyle == 'video'
                <div class="d-flex justify-content-center">
                    <div class="ratio ratio-$image_item.get('lightboxVideoApect', '4x3')">
                        <video id="imageCarousel-$imageCount-ModalVideo" controls >
                            <source id="videoSource" src="$image_item.imageLink" />
                        </video>
                    </div>
                </div>
                #else 
                <img src="$image_item.imageUrl" alt="$image_item.imageCaptionHeading" class="mw-100">
                #end if
            </div>
            <div class="modal-footer"></div>
        </div>
    </div>
</div>
<script>
document.getElementById('imageCarousel-$imageCount-Modal').addEventListener('shown.bs.modal', function () {
    var video = document.getElementById('imageCarousel-$imageCount-ModalVideo');
    video.pause();
    video.currentTime = 0;
    video.play();
})
</script>
#end if
#set $imageCount += 1
#end for
#end if
<script language='javascript'>
 function imageRefresh(img, timeout) {
    if (timeout > 0) {
        setTimeout(function() {
            img.src = img.src+'';
        }, timeout);
    }
  }
</script>