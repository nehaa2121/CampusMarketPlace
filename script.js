document.addEventListener("DOMContentLoaded", function () {

    // ------------------------------------------
    // 1. AUTO-HIDE FLASH MESSAGES
    // ------------------------------------------

    const flashMessages = document.querySelectorAll(".flash");

    flashMessages.forEach(function (message) {
        window.setTimeout(function () {
            message.style.transition = "opacity 300ms ease";
            message.style.opacity = "0";

            window.setTimeout(function () {
                message.remove();
            }, 350);

        }, 4500);
    });


    // ------------------------------------------
    // 2. SEARCH PRICE VALIDATION
    // ------------------------------------------

    const searchForm = document.getElementById("search-form");
    const minPrice = document.getElementById("min-price");
    const maxPrice = document.getElementById("max-price");

    if (searchForm && minPrice && maxPrice) {

        searchForm.addEventListener("submit", function (event) {

            const minimum = minPrice.value.trim();
            const maximum = maxPrice.value.trim();

            if (
                minimum !== "" &&
                maximum !== "" &&
                Number(minimum) > Number(maximum)
            ) {
                event.preventDefault();

                alert(
                    "Minimum price cannot be greater than maximum price."
                );

                minPrice.focus();
            }

            if (
                minimum !== "" && Number(minimum) < 0 ||
                maximum !== "" && Number(maximum) < 0
            ) {
                event.preventDefault();

                alert("Price cannot be negative.");
            }
        });
    }


    // ------------------------------------------
    // 3. SELL ITEM PHOTO PREVIEW
    // ------------------------------------------

    const photoInput = document.getElementById("photo");
    const previewContainer =
        document.getElementById("preview-container");
    const photoPreview =
        document.getElementById("photo-preview");
    const removePhotoButton =
        document.getElementById("remove-photo");

    const MAX_FILE_SIZE = 5 * 1024 * 1024;

    const ALLOWED_TYPES = [
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp"
    ];

    if (
        photoInput &&
        previewContainer &&
        photoPreview &&
        removePhotoButton
    ) {

        let previewURL = null;

        function clearPhotoPreview() {

            if (previewURL) {
                URL.revokeObjectURL(previewURL);
                previewURL = null;
            }

            photoPreview.removeAttribute("src");
            previewContainer.hidden = true;
        }


        photoInput.addEventListener("change", function () {

            const file = photoInput.files[0];

            clearPhotoPreview();

            if (!file) {
                return;
            }


            // Check image format.
            if (!ALLOWED_TYPES.includes(file.type)) {

                alert(
                    "Invalid image format. Please choose a JPG, PNG, GIF or WEBP image."
                );

                photoInput.value = "";
                return;
            }


            // Check image size.
            if (file.size > MAX_FILE_SIZE) {

                alert("Image size must not exceed 5 MB.");

                photoInput.value = "";
                return;
            }


            // Preview selected image.
            previewURL = URL.createObjectURL(file);

            photoPreview.src = previewURL;
            previewContainer.hidden = false;
        });


        // Remove the selected photo.
        removePhotoButton.addEventListener("click", function () {

            photoInput.value = "";

            clearPhotoPreview();
        });

    }


    // ------------------------------------------
    // 4. CONTACT FORM VALIDATION
    // ------------------------------------------

    const contactForm = document.querySelector(".contact-form");

    if (contactForm) {

        contactForm.addEventListener("submit", function (event) {

            const message = document.getElementById("message");

            if (!message || !message.value.trim()) {

                event.preventDefault();

                alert("Please write a message before submitting.");

                if (message) {
                    message.focus();
                }
            }
        });
    }


    // ------------------------------------------
    // 5. PREVENT EMPTY SEARCH SUBMISSION ISSUES
    // ------------------------------------------

    const searchInput = document.getElementById("search-q");

    if (searchInput) {
        searchInput.addEventListener("keydown", function (event) {

            if (event.key === "Escape") {
                searchInput.value = "";
            }
        });
    }

});
