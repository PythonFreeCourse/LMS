function trackFinished(solutionId, element) {
  element.addEventListener('click', () => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `/checked/${solutionId}`, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.responseType = 'json';
    xhr.onreadystatechange = () => {
      if (xhr.readyState === 4) {
        if (xhr.status === 200) {
          window.location.href = xhr.response.next;
        } else {
          console.log(xhr.status);
        }
      }
    };

    xhr.send(JSON.stringify({}));
  });
}


function sendComment(kind, solutionId, line, commentData) {
  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/comments')
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.responseType = 'json';
  xhr.onreadystatechange = () => {
    if (xhr.readyState === 4) {
      if (xhr.status === 200) {
        const commentFullData = commentData;
        commentFullData.id = xhr.response.id;
        commentFullData.text = xhr.response.text;
        window.addCommentToLine(line, commentFullData);
      } else {
        console.log(xhr.status);
      }
    }
  };

  xhr.send(
    JSON.stringify({
      act: 'create',
      solution: solutionId,
      line,
      comment: commentData,
      kind, // Should be 'text' or 'id'
    }),
  );
}

function visuallyRemoveComment(commentId) {
  const commentElement = document.querySelector(`.grader-delete[data-commentid="${commentId}"]`).closest('.comment');
  const lineElement = document.querySelector(`.line[data-line="${commentElement.dataset.line}"]`);
  const hr = commentElement.nextElementSibling || commentElement.previousElementSibling;
  if (hr === null) {
    lineElement.dataset.marked = false;
    window.markLine(lineElement, false);
    $(lineElement).popover('dispose');
  } else {
    hr.parentNode.removeChild(hr);
    commentElement.parentNode.removeChild(commentElement);
  }
}


function deleteComment(solutionId, commentId) {
  const xhr = new XMLHttpRequest();
  const url = `/comments?act=delete&solutionId=${solutionId}&commentId=${commentId}`;
  xhr.open('GET', url, true);
  xhr.setRequestHeader('Content-Type', 'application/json');
  xhr.responseType = 'json';
  xhr.onreadystatechange = () => {
    if (xhr.readyState === 4) {
      if (xhr.status === 200) {
        visuallyRemoveComment(commentId);
      } else {
        console.log(xhr.status);
      }
    }
  };

  xhr.send('');
}

function sendNewComment(solutionId, line, commentText) {
  return sendComment('text', solutionId, line, commentText);
}


function sendExistsComment(solutionId, line, commentId) {
  return sendComment('id', solutionId, line, commentId);
}


function trackDragAreas(items) {
  function findElementToMark(e) {
    const span = (e.target.nodeType === 3) ? e.target.parentNode : e.target;
    const target = span.closest('.line');
    return target;
  }

  Array.from(items).forEach((item) => {
    item.addEventListener('dragover', (e) => {
      e.preventDefault();
      window.markLine(findElementToMark(e), true);
    }, false);
    item.addEventListener('dragleave', (e) => {
      e.preventDefault();
      window.markLine(findElementToMark(e), false);
    }, false);
    item.addEventListener('dragenter', (e) => {
      e.preventDefault();
    }, false);
    item.addEventListener('mouseenter', (e) => {
      e.preventDefault();
      window.markLine(findElementToMark(e), true);
    }, false);
    item.addEventListener('mouseleave', (e) => {
      e.preventDefault();
      window.markLine(findElementToMark(e), false);
    }, false);
    item.addEventListener('drop', (e) => {
      e.preventDefault();
      const target = findElementToMark(e);
      const { line } = target.dataset;
      const commentId = e.dataTransfer.getData('text/plain');
      window.markLine(target, false);
      sendExistsComment(window.solutionId, line, commentId);
    }, false);
  });
}


function trackDraggables(elements) {
  Array.from(elements).forEach((item) => {
    item.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('text/plain', e.target.dataset.commentid);
    });
  });
}


function trackTextArea(lineNumber) {
  const target = `textarea[data-line='${lineNumber}']`;
  const popoverElement = `.grader-add[data-line='${lineNumber}']`;
  $(target).keypress((e) => {
    if (e.ctrlKey && e.keyCode === 13) {
      sendNewComment(window.solutionId, lineNumber, e.target.value);
      $(popoverElement).popover('hide');
    }
  });
}


function registerNewCommentPopover(element) {
  const lineNumber = element.dataset.line;
  $(element).popover({
    html: true,
    title: `הערה חדשה לשורה ${lineNumber}`,
    sanitize: false,
    content: `<textarea data-line='${lineNumber}'></textarea>`,
  });
  $(element).on('inserted.bs.popover', () => {
    trackTextArea(lineNumber);
  });
}


function addNewCommentButtons(elements) {
  Array.from(elements).forEach((item, lineNumber) => {
    const newNode = document.createElement('span');
    newNode.className = 'grader-add';
    newNode.dataset.line = lineNumber + 1;
    newNode.innerHTML = '<i class="fa fa-plus" aria-hidden="true"></i>';
    item.parentNode.insertBefore(newNode, item);
    registerNewCommentPopover(newNode);
  });
  $('[data-toggle=popover]').popover();
}


window.deleteComment = deleteComment;
window.addEventListener('lines-numbered', () => {
  trackDragAreas(document.getElementsByClassName('line'));
  trackDraggables(document.getElementsByClassName('known-comment'));
  trackFinished(window.solutionId, document.getElementById('save-check'));
  addNewCommentButtons(document.getElementsByClassName('line'));
  if (!window.isUserGrader()) {
    sessionStorage.setItem('role', 'grader');
  }


  /*
  // Select the node that will be observed for mutations
  const solutionId = 1; // # TODO: Fetch from URL
  const targetNode = document.body;

  // Options for the observer (which mutations to observe)
  const config = { attributes: true, childList: true, subtree: true };

  // Callback function to execute when mutations are observed
  const callback = ((mutationsList) => {
    // Use traditional 'for loops' for IE 11
    mutationsList.forEach((mutation) => {
      if (mutation.type === 'childList') {
        mutation.addedNodes.forEach((node) => {
          const deleteButton = node.querySelector('.grader-delete');
          console.log(deleteButton);
          deleteButton.addEventListener('click', () => {
            deleteComment(solutionId, deleteButton.dataset.commentid);
          });
        });
      }
    });
  });

  // Create an observer instance linked to the callback function
  const observer = new MutationObserver(callback);

  // Start observing the target node for configured mutations
  observer.observe(targetNode, config);
  */
});
