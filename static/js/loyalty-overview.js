(function () {
  var search = document.getElementById("loyalty-search-q");
  if (!search || !search.form) return;
  search.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      e.preventDefault();
      search.form.submit();
    }
  });
})();
