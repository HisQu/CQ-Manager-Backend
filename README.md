# CQ Manager Backend


The repository containing the frontend can be found here: https://github.com/HerrMotz/Competency-Question-Manager-Frontend

A student project by:
- Dominik Buschhold (Backend)
- Malte Weber (Backend)
- Chiara Tunc (UX)
- Daniel Motz (Frontend)


## Functionality
This tool enables team collaboration on Competency Questions for Ontologies.

## Roles

The backend currently distinguishes the following roles and access levels:

- **Unverified user**: Can authenticate but is blocked from protected endpoints until verified.
- **Verified user**: Base authenticated role for regular API usage.
- **System administrator**: Global admin role (`is_system_admin`) for user administration and elevated operations.
- **Project manager**: Project-scoped role for project and group management operations.
- **Ontology engineer**: Project-scoped role for ontology editing workflows (including term/annotation editing and term deletion).
- **Project member**: User that belongs to at least one group within a project; can access project member routes.
- **Group member**: User assigned to a group; can access group member routes.

### Permission headers

For project and group scoped endpoints, the API adds permission headers to responses:

- `Permissions-Project-Manager`
- `Permissions-Project-Engineer`
- `Permissions-Project-Member`
- `Permissions-Group-Member`

These headers are derived from the authenticated user and the `project_id` / `group_id` path context.

## User deletion behavior

`DELETE /users/{user_email}` enforces database referential integrity.

- If the user has no remaining references, deletion succeeds with `204 No Content`.
- If the user is still referenced by related records, deletion is blocked and returns `409 Conflict`.
- Error detail explains that related records must be removed or reassigned first.

Typical references that block deletion include:

- `question.author_id`, `question.editor_id`
- `comment.author_id`
- `rating.author_id`
- `version.editor_id`
- `consolidation.engineer_id`
- membership/role tables (`group_members`, `project_managers`, `project_engineers`)

This behavior is intentional to prevent orphaned records.

## To Developers

If you have an IDE like PyCharm you can configure your Run target as follows:
![image](https://github.com/user-attachments/assets/a0d2f817-4cdf-4400-bf2d-9c399ee773b8)

This will allow you to e.g. attach a debugger.

The [documentation](https://docs.litestar.dev/2/usage/debugging.html) has an entry on this as well.
